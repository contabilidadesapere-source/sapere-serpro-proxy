"""
SERPRO mTLS Proxy — Sapere
Baseado no servidor do pacote serpro_integra_contador_api (Marlon Santos),
adaptado para deploy no Render:
  - Certificado/credenciais lidos de variáveis de ambiente (não trafegam do front)
  - Proteção por chave de API (header X-Proxy-Key)
  - Endpoint combinado /integra (autentica + consulta numa só chamada)
"""

import os
import logging
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from business_logic import (
    process_autenticar_serpro,
    process_autenticar_procurador,
    process_proxy_serpro,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("serpro-proxy")

# ===== Configuração via ambiente =====
ENV = {
    "consumer_key": os.environ.get("SERPRO_CONSUMER_KEY", ""),
    "consumer_secret": os.environ.get("SERPRO_CONSUMER_SECRET", ""),
    "certificado_base64": os.environ.get("SERPRO_CERT_BASE64", ""),
    "certificado_senha": os.environ.get("SERPRO_CERT_SENHA", ""),
    "contratante_numero": os.environ.get("SERPRO_CONTRATANTE_NUMERO", ""),
    "autor_pedido_dados_numero": os.environ.get("SERPRO_AUTOR_NUMERO", ""),
    "ambiente": os.environ.get("SERPRO_AMBIENTE", "producao"),
}
PROXY_API_KEY = os.environ.get("PROXY_API_KEY", "")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")


def _merge_env(data: Dict[str, Any]) -> Dict[str, Any]:
    """Preenche credenciais/certificado/ambiente a partir do ambiente quando ausentes."""
    out = dict(data or {})
    for k, v in ENV.items():
        if v and not out.get(k):
            out[k] = v
    return out


def require_key(x_proxy_key: Optional[str] = Header(default=None)):
    """Exige a chave de API se PROXY_API_KEY estiver configurada."""
    if PROXY_API_KEY and x_proxy_key != PROXY_API_KEY:
        raise HTTPException(status_code=401, detail="Chave de API inválida (X-Proxy-Key).")
    return True


app = FastAPI(title="Sapere SERPRO mTLS Proxy", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== Models =====
class AutenticarRequest(BaseModel):
    consumer_key: Optional[str] = None
    consumer_secret: Optional[str] = None
    contratante_numero: Optional[str] = None
    autor_pedido_dados_numero: Optional[str] = None
    ambiente: Optional[str] = None
    certificado_base64: Optional[str] = None
    certificado_senha: Optional[str] = None


class ProxyRequest(BaseModel):
    endpoint: str
    body: Dict[str, Any]
    access_token: str
    jwt_token: str
    procurador_token: Optional[str] = None
    ambiente: Optional[str] = None
    certificado_base64: Optional[str] = None
    certificado_senha: Optional[str] = None


class IntegraRequest(BaseModel):
    """Autentica e consulta num passo só. Só precisa de endpoint + body."""
    endpoint: str
    body: Dict[str, Any]
    ambiente: Optional[str] = None
    contratante_numero: Optional[str] = None
    autor_pedido_dados_numero: Optional[str] = None


# ===== Endpoints =====
@app.get("/")
async def root():
    configured = bool(ENV["consumer_key"] and ENV["certificado_base64"])
    return {
        "status": "online",
        "service": "Sapere SERPRO mTLS Proxy",
        "ambiente": ENV["ambiente"],
        "credenciais_configuradas": configured,
        "protegido_por_chave": bool(PROXY_API_KEY),
        "endpoints": [
            "POST /autenticar_serpro",
            "POST /autenticar_procurador",
            "POST /proxy_serpro",
            "POST /integra  (autentica + consulta)",
        ],
    }


@app.post("/autenticar_serpro")
async def autenticar_serpro(req: AutenticarRequest, _=Depends(require_key)):
    try:
        return process_autenticar_serpro(_merge_env(req.model_dump()), get_secret_fn=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("autenticar_serpro: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/autenticar_procurador")
async def autenticar_procurador(req: Dict[str, Any], _=Depends(require_key)):
    try:
        return process_autenticar_procurador(_merge_env(req), get_secret_fn=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("autenticar_procurador: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/proxy_serpro")
async def proxy_serpro(req: ProxyRequest, _=Depends(require_key)):
    try:
        return process_proxy_serpro(_merge_env(req.model_dump()), get_secret_fn=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("proxy_serpro: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/integra")
async def integra(req: IntegraRequest, _=Depends(require_key)):
    """Autentica no SERPRO (env) e executa a consulta no endpoint informado."""
    try:
        auth_in = _merge_env({
            "ambiente": req.ambiente,
            "contratante_numero": req.contratante_numero,
            "autor_pedido_dados_numero": req.autor_pedido_dados_numero,
        })
        auth = process_autenticar_serpro(auth_in, get_secret_fn=None)

        proxy_in = _merge_env({
            "endpoint": req.endpoint,
            "body": req.body,
            "ambiente": req.ambiente,
            "access_token": auth.get("access_token"),
            "jwt_token": auth.get("jwt_token"),
        })
        return process_proxy_serpro(proxy_in, get_secret_fn=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("integra: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
