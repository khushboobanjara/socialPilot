import json, re
import httpx
from app.core.config import settings

class AIServiceError(RuntimeError): pass

def check_ollama():
    try:
        r=httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=5); r.raise_for_status()
        names=[m.get('name','') for m in r.json().get('models',[])]
        ok=any(n == settings.ollama_model or n.startswith(settings.ollama_model+':') for n in names)
        return {"available":ok,"model":settings.ollama_model,"installed_models":names}
    except (httpx.HTTPError, ValueError):
        return {"available":False,"model":settings.ollama_model,"installed_models":[],"detail":"Ollama is not reachable; start Ollama and check the model."}

def parse_json(text):
    text=re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip(), flags=re.I)
    try: return json.loads(text)
    except json.JSONDecodeError:
        a,b=text.find('{'),text.rfind('}')
        if a>=0 and b>a:
            try:return json.loads(text[a:b+1])
            except json.JSONDecodeError: pass
        raise AIServiceError('AI returned invalid JSON. Please try again.')

def generate_platform_content(business, topic, goal, content_type, platforms, offer_details, include_emojis):
    allowed={'instagram','facebook','linkedin'}
    if not platforms or any(p not in allowed for p in platforms): raise AIServiceError('Unsupported platform selected.')
    system='''You are a professional small-business social media strategist. Return ONLY valid JSON with schema {"variants":[{"platform":"instagram","caption":"...","hashtags":["#tag"],"call_to_action":"..."}]}. Create exactly one variant per requested platform. Instagram: engaging and visual-first; Facebook: community-friendly; LinkedIn: professional and useful. Write in the business profile language. Use 5-12 relevant hashtags. Do not invent prices, offers, guarantees, addresses, testimonials, or facts. Hashtags do not guarantee reach. No markdown fences.'''
    context={"business":{"name":business.name,"category":business.category,"description":business.description,"target_audience":business.target_audience,"language":business.language,"brand_voice":business.brand_voice},"request":{"topic":topic,"goal":goal,"content_type":content_type,"platforms":platforms,"offer_details":offer_details or "No offer details provided","include_emojis":include_emojis}}
    try:
        r=httpx.post(f"{settings.ollama_base_url.rstrip('/')}/api/chat",json={"model":settings.ollama_model,"stream":False,"format":"json","messages":[{"role":"system","content":system},{"role":"user","content":json.dumps(context,ensure_ascii=False)}],"options":{"temperature":0.7}},timeout=settings.ollama_timeout_seconds)
        r.raise_for_status(); raw=r.json().get('message',{}).get('content','')
    except httpx.ConnectError as e: raise AIServiceError('Cannot connect to Ollama. Start Ollama and install the configured model.') from e
    except httpx.TimeoutException as e: raise AIServiceError('AI generation timed out. Try again or use a smaller local model.') from e
    except httpx.HTTPStatusError as e: raise AIServiceError(f'Ollama returned HTTP {e.response.status_code}. Check the model name.') from e
    except (httpx.HTTPError,ValueError) as e: raise AIServiceError('Could not communicate with Ollama.') from e
    data=parse_json(raw); rows=data.get('variants')
    if not isinstance(rows,list): raise AIServiceError('AI response did not contain a variants list.')
    found={}
    for item in rows:
        if not isinstance(item,dict): continue
        platform=str(item.get('platform','')).lower().strip(); caption=item.get('caption','')
        if platform not in platforms or platform in found or not isinstance(caption,str) or not caption.strip(): continue
        tags=item.get('hashtags',[]); tags=tags if isinstance(tags,list) else []
        clean=[]
        for tag in tags:
            if isinstance(tag,str) and tag.strip():
                tag=tag.strip().replace(' ',''); tag=tag if tag.startswith('#') else '#'+tag
                if tag not in clean: clean.append(tag[:80])
        found[platform]={"platform":platform,"caption":caption.strip()[:10000],"hashtags":clean[:30],"call_to_action":str(item.get('call_to_action','')).strip()[:500]}
    if any(p not in found for p in platforms): raise AIServiceError('AI did not return every selected platform. Please try again.')
    return [found[p] for p in platforms]
