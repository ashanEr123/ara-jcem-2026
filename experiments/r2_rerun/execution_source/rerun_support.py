"""Recorded API calls, explicit output validation, and a batch circuit breaker."""
import json, math, os, re, time, traceback
from datetime import datetime, timezone

class ProviderHalt(RuntimeError):
    """Must propagate through agent fallback handlers and stop the batch."""

class OutputLimitError(ValueError): pass
class EmptyOutputError(ValueError): pass
class InvalidOutputError(ValueError): pass

def utc(): return datetime.now(timezone.utc).isoformat()

def redact(value):
    text=str(value)
    for key in ('OPENAI_API_KEY','MISTRAL_API_KEY'):
        secret=os.getenv(key)
        if secret:text=text.replace(secret,'[REDACTED]')
    text=re.sub(r'sk-[A-Za-z0-9_-]+','[REDACTED]',text)
    return re.sub(r'(?i)Bearer\s+[A-Za-z0-9._-]+','Bearer [REDACTED]',text)

def error_details(exc):
    body=getattr(exc,'body',None)
    if isinstance(body,dict):
        inner=body.get('error',body)
        code=inner.get('code') if isinstance(inner,dict) else None
    else:code=None
    return {'error_type':type(exc).__name__,'message':redact(exc),
            'http_status':getattr(exc,'status_code',None),
            'provider_code':getattr(exc,'code',None) or code,
            'request_id':getattr(exc,'request_id',None),
            'body':redact(json.dumps(body,default=str)) if body is not None else None,
            'traceback':redact(traceback.format_exc())}

def fatal_error(exc):
    status=getattr(exc,'status_code',None)
    text=(str(exc)+' '+str(getattr(exc,'body',''))).lower()
    return (status in (400,401,403,404,422,429) or
            any(s in text for s in ('deactivated','account disabled','insufficient_quota',
                                    'billing_hard_limit','invalid_api_key')) or
            type(exc).__name__ in ('AuthenticationError','PermissionDeniedError','RateLimitError'))

def validate_response(response,json_mode=False):
    choices=response.choices
    if not choices:raise EmptyOutputError('No response choices')
    choice=choices[0]
    finish=choice.finish_reason
    if finish in ('length','max_tokens'):
        raise OutputLimitError('Completion token limit reached; inspect saved token usage and content')
    if finish!='stop':raise InvalidOutputError(f'Unexpected finish reason: {finish}')
    answer=choice.message.content
    if not isinstance(answer,str) or not answer.strip():raise EmptyOutputError('Empty/non-text model response')
    if not json_mode:return answer
    try:data=json.loads(answer.replace('```json','').replace('```','').strip())
    except (ValueError,TypeError) as e:raise InvalidOutputError('Invalid JSON response') from e
    if not isinstance(data,dict):raise InvalidOutputError('JSON response must be an object')
    if 'actions' in data:
        aa=data['actions']
        if not isinstance(aa,list) or not aa or any(not isinstance(a,dict) or a.get('type') not in ('query','answer') or not isinstance(a.get('content'),str) or not a['content'].strip() for a in aa):
            raise InvalidOutputError('Invalid or empty actions array')
    elif 'scores' in data:
        ss=data['scores']
        if not isinstance(ss,list) or not ss or any(isinstance(s,bool) or not isinstance(s,(float,int)) or not math.isfinite(s) or not 0<=s<=10 for s in ss):
            raise InvalidOutputError('Scores must be finite numbers between 0 and 10')
    else:raise InvalidOutputError('Expected actions or scores in JSON response')
    return data

class Gateway:
    last_request=0
    def __init__(self,settings):
        self.settings=settings;self.events=[]

    def invoke(self,fn,event):
        """Retry only transport/5xx errors, never quota/access/unknown 429 errors."""
        self.events.append(event);event['attempts']=[]
        max_attempts=self.settings['max_transport_attempts']
        for attempt in range(max_attempts):
            wait=max(0,self.settings['min_request_interval_s']-(time.monotonic()-Gateway.last_request))
            if wait:time.sleep(wait)
            Gateway.last_request=time.monotonic()
            record={'started_utc':utc()};event['attempts'].append(record);start=time.perf_counter()
            try:
                result=fn();record['status']='ok';return result
            except Exception as exc:
                info=error_details(exc);record.update(status='failed',error=info)
                if fatal_error(exc):
                    event['fatal_error']=info
                    raise ProviderHalt('Provider rejected request; batch stopped. '+info['message']) from exc
                status=info['http_status']
                transient=(isinstance(status,int) and status>=500) or type(exc).__name__ in ('APITimeoutError','APIConnectionError','TimeoutException','ConnectError','ReadTimeout')
                if not transient or attempt+1==max_attempts:raise
                time.sleep(self.settings['retry_wait_s']*(attempt+1))
            finally:record['elapsed_s']=time.perf_counter()-start

class Recorder:
    def __init__(self):
        import r2
        self.calls=[];self.retrievals=[];self.embeddings=[];self.fallbacks=[]
        self.gateway=Gateway(r2.STUDY['rerun'])

    def completion(self,messages,temperature=.2,max_tokens=1024,json_mode=False,provider='openai',model=None):
        import r2
        from ara import llm
        model=model or r2.STUDY['models']['generator']
        budget=r2.STUDY['rerun']['structured_completion_tokens' if json_mode else 'final_completion_tokens']
        call={'provider':provider,'requested_model':model,'messages':messages,
              'temperature_requested':temperature,'pipeline_token_request':max_tokens,
              'max_tokens_requested':budget,'json_mode':json_mode,'started_utc':utc()}
        self.calls.append(call);start=time.perf_counter()
        try:
            if provider=='openai':
                kwargs=llm._chat_kwargs(model,temperature,budget)
                if json_mode:kwargs['response_format']={'type':'json_object'}
                call['request_parameters']=kwargs
                result=self.gateway.invoke(lambda:llm._client.chat.completions.create(model=model,messages=messages,**kwargs),call)
            else:
                call['request_parameters']={'temperature':temperature,'max_tokens':budget}
                result=self.gateway.invoke(lambda:r2.mistral().chat.complete(model=model,messages=messages,temperature=temperature,max_tokens=budget),call)
            call['response']=r2.dump(result)
            call['request_id']=getattr(result,'_request_id',None)
            data=validate_response(result,json_mode)
            if json_mode and messages and 'process reward model' in messages[0]['content']:
                expected=len(re.findall(r'^\d+\. \[',messages[-1]['content'],re.M))
                if len(data.get('scores',[]))!=expected:raise InvalidOutputError('Score count does not match candidate count')
            return data
        except Exception as exc:
            call['error_type']=type(exc).__name__;call['error']=error_details(exc);raise
        finally:call['elapsed_s']=time.perf_counter()-start

    def embed(self,texts):
        import r2,config
        from ara import llm
        if isinstance(texts,str):texts=[texts]
        event={'provider':'openai','kind':'embedding','model':config.EMBED_MODEL,'started_utc':utc(),'input_count':len(texts)}
        self.embeddings.append(event)
        try:
            result=self.gateway.invoke(lambda:llm._client.embeddings.create(model=config.EMBED_MODEL,input=texts),event)
            event['request_id']=getattr(result,'_request_id',None)
            event['usage']=result.usage.model_dump() if getattr(result,'usage',None) else None
            return [d.embedding for d in result.data]
        except Exception as exc:event['error']=error_details(exc);raise

    def note_fallback(self,kind):self.fallbacks.append({'kind':kind,'utc':utc()})
