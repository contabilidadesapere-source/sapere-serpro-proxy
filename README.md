# Sapere SERPRO mTLS Proxy

Proxy HTTP que faz a integração com a **API SERPRO Integra Contador** usando
**mTLS** (certificado digital A1), assinatura XML de procurador e o proxy
genérico que cobre **todos os serviços** do Integra Contador.

Baseado no servidor Python do pacote
[`serpro_integra_contador_api`](https://github.com/MarlonSantosDev/serpro_integra_contador_api)
(MIT, Marlon Santos), adaptado para rodar no **Render** com:
- certificado e credenciais lidos de **variáveis de ambiente** (não trafegam do front);
- proteção por **chave de API** (`X-Proxy-Key`);
- endpoint combinado **`/integra`** (autentica + consulta numa só chamada).

## Por que um serviço separado?
O SERPRO exige autenticação mTLS com certificado de cliente. Ambientes serverless
como Supabase Edge Functions (Deno) e Vercel não suportam isso de forma confiável,
por isso a integração roda aqui, num serviço Python (FastAPI) que suporta mTLS.

## Deploy no Render
1. Suba este diretório para um repositório no GitHub.
2. No Render: New → Web Service → conecte o repositório.
3. Build: `pip install -r requirements.txt` · Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Em **Environment**, adicione as variáveis do `.env.example` (com seus valores reais).

### Converter o certificado .pfx em base64
- Linux/Mac: `base64 -w0 certificado.pfx > cert.b64`
- Windows (PowerShell): `[Convert]::ToBase64String([IO.File]::ReadAllBytes("certificado.pfx")) > cert.b64`
Cole o conteúdo de `cert.b64` em `SERPRO_CERT_BASE64`.

## Endpoints
- `GET /` — health check / status da configuração
- `POST /autenticar_serpro` — OAuth2 + mTLS, retorna tokens
- `POST /autenticar_procurador` — autenticação com assinatura XML de procurador
- `POST /proxy_serpro` — chamada genérica a qualquer serviço (precisa de tokens)
- `POST /integra` — **recomendado**: autentica e consulta de uma vez

### Exemplo `/integra`
```json
{
  "endpoint": "/Apoiar",
  "body": { "...": "payload do serviço SERPRO" }
}
```
Cabeçalho: `X-Proxy-Key: <sua PROXY_API_KEY>`
