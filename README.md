# Monitor de presença Roblox

Programa para Render Cron Job que consulta a API oficial de presença do Roblox e envia alertas via ntfy após detectar mudança observada de offline para online.

### Render
- Runtime: Python
- Build command: `python -m py_compile monitor.py`
- Start command: `python monitor.py`
- Cron (UTC): `*/5 * * * *`
- Variáveis de ambiente (definir no Render, **não** no GitHub): `ROBLOX_USER_ID`, `NTFY_TOPIC`, `NTFY_STATE_TOPIC`

Para receber os alertas, assine no aplicativo ntfy o tópico correspondente a `NTFY_TOPIC` no servidor https://ntfy.sh.

A primeira execução somente registra o estado inicial, pois uma observação isolada de online não demonstra uma entrada recente. Consultas com resultado `0` podem incluir restrições de visibilidade, não provando que o usuário saiu. Quando Roblox não disponibilizar uma resposta válida, o programa não emite alerta. O ntfy público não oferece persistência garantida para o estado; eventuais falhas podem impedir alertas.

Sem credenciais ou cookies Roblox. Não contorna controles de privacidade.
