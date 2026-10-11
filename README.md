# DailyBrief 📰

Resumo diário de notícias gerado por IA — 100% automatizado no GitHub.

## Como colocar no ar em 5 minutos

### 1. Criar o repositório público

```bash
gh repo create news-digest --public --source=. --remote=origin --push
```

Ou crie manualmente em [github.com/new](https://github.com/new) (público) e faça push deste diretório.

### 2. Adicionar os Secrets

No repositório → **Settings → Secrets and variables → Actions → New repository secret**:

| Nome | Valor |
|------|-------|
| `GEMINI_API_KEY` | Sua chave do [Google AI Studio](https://aistudio.google.com/apikey) |
| `GROQ_API_KEY` | Sua chave do [Groq Console](https://console.groq.com/keys) |

> Pelo menos uma das chaves é necessária. O pipeline usa Gemini como primário e Groq como fallback.

### 3. Ativar o GitHub Pages

**Settings → Pages → Source:** `Deploy from a branch` → branch `main`, pasta `/docs` → **Save**.

O site estará em: `https://<seu-usuario>.github.io/news-digest/`

### 4. Rodar o workflow manualmente (primeira vez)

**Actions → Daily News Digest → Run workflow** → **Run workflow**.

Aguarde ~5–10 min. O Action vai coletar, resumir e publicar automaticamente.

A partir daí, roda todo dia às **07:00 horário de Brasília** sem precisar de nada da sua parte.

---

## Arquitetura

```
news-digest/
├── .github/workflows/daily.yml   # Cron + commit automático
├── src/
│   ├── main.py                   # Ponto de entrada
│   ├── collect.py                # HN + Reddit + RSS
│   ├── extract.py                # trafilatura + fallback
│   ├── llm.py                    # Router Gemini → Groq (circuit breaker)
│   └── pipeline.py               # Classificação + resumo (prompts PT-BR)
├── docs/                         # GitHub Pages
│   ├── index.html                # PWA mobile-first
│   ├── app.js                    # SPA com roteamento por hash
│   ├── style.css                 # Tema escuro automático
│   ├── manifest.json             # PWA manifest
│   ├── sw.js                     # Service worker (cache offline)
│   ├── data.json                 # Dados do dia atual
│   └── archive/                  # Histórico por data
├── config.yaml                   # Fontes, temas, limites, LLM
└── requirements.txt
```

## Personalização

Edite [`config.yaml`](config.yaml) para:
- Adicionar/remover subreddits
- Adicionar feeds RSS
- Ajustar limites de coleta e rate limits do LLM
- Trocar modelos de IA

## Fontes coletadas

| Fonte | Tipo | Necessita API? |
|-------|------|---------------|
| Hacker News | API oficial | ❌ |
| Reddit (8 subreddits) | RSS + JSON | ❌ |
| BBC Brasil, G1, CNN Brasil | RSS | ❌ |
| TechCrunch, The Verge, Ars Technica | RSS | ❌ |
| MIT Technology Review, Nature | RSS | ❌ |

## Tecnologias

- **Python 3.11**: `requests`, `feedparser`, `trafilatura`, `pyyaml`
- **LLM**: Google Gemini 2.0 Flash → Groq llama-3.3-70b (fallback)
- **Site**: HTML + CSS + JS puro, PWA instalável
- **CI/CD**: GitHub Actions (cron diário + manual)
