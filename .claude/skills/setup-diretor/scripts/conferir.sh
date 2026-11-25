#!/usr/bin/env bash
# conferir.sh: o que o Mac do diretor já tem para planejar e prototipar (skill /setup-diretor).
#
# Uma linha por item, na ordem das Partes do passo a passo: OK, FALTA (conta, exit 1)
# ou AVISO (não conta), com o conserto ao lado. O Claude começa pela primeira FALTA.
# Nunca imprime valor de chave. Não confere nada de produção: o diretor não tem
# Coolify, token nem acesso de escrita, de propósito.

set -u
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
APP="$RAIZ/hospital-reunioes"
UPSTREAM="pedrorezendefig/hospital-reunioes"
FALHAS=0
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/node@22/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

ok()    { printf '  OK     %-30s %s\n' "$1" "${2:-}"; }
falta() { printf '  FALTA  %-30s %s\n' "$1" "${2:-}"; FALHAS=$((FALHAS+1)); }
aviso() { printf '  AVISO  %-30s %s\n' "$1" "${2:-}"; }
titulo(){ printf '\n%s\n' "$1"; }
tem()   { command -v "$1" >/dev/null 2>&1; }
versao_min() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" = "$2" ]; }

titulo "Parte 2. Ferramentas"
tem brew && ok "Homebrew" || falta "Homebrew" "no Terminal, o comando do passo a passo (pede a senha do Mac)"
for par in "git:git" "gh:gh" "jq:jq" "uv:uv" "supabase:supabase/tap/supabase"; do
  bin="${par%%:*}"; formula="${par#*:}"
  tem "$bin" && ok "$bin" || falta "$bin" "brew install $formula"
done
if tem node; then
  v="$(node --version | tr -d v)"
  versao_min "$v" "22.12" && ok "Node" "$v" || falta "Node" "tem $v, precisa 22.12 ou mais: brew install node@22 && brew link --overwrite --force node@22"
else
  falta "Node" "brew install node@22 && brew link --overwrite --force node@22"
fi
if tem corepack && COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm@9 --version >/dev/null 2>&1; then
  ok "pnpm@9 (corepack)"
else
  falta "pnpm@9 (corepack)" "corepack enable && echo y | corepack pnpm@9 --version"
fi
if tem docker && docker ps >/dev/null 2>&1; then
  ok "Docker"
elif [ -d /Applications/Docker.app ]; then
  falta "Docker" "instalado, mas parado: abra o Docker Desktop e espere a baleia parar"
else
  falta "Docker" "baixar https://desktop.docker.com/mac/main/arm64/Docker.dmg"
fi

titulo "Parte 3. GitHub e a cópia"
LOGIN=""
if tem gh && gh auth status >/dev/null 2>&1; then
  LOGIN="$(gh api user --jq .login 2>/dev/null)"
  ok "gh conectado" "$LOGIN"
else
  falta "gh conectado" "no Terminal: gh auth login --web --git-protocol https --hostname github.com"
fi
origin="$(git -C "$RAIZ" remote get-url origin 2>/dev/null)"
upstream="$(git -C "$RAIZ" remote get-url upstream 2>/dev/null)"
case "$origin" in
  *"$UPSTREAM"*) falta "origin no fork" "origin aponta o repositório do time; o diretor trabalha no fork: gh repo fork $UPSTREAM --remote" ;;
  *"/hospital-reunioes"*|*"/hospital-reunioes.git") ok "origin no fork" "$origin" ;;
  *) falta "origin no fork" "cd ~ && gh repo fork $UPSTREAM --clone --default-branch-only" ;;
esac
case "$upstream" in
  *"$UPSTREAM"*) ok "upstream no time" ;;
  *) falta "upstream no time" "git remote add upstream https://github.com/$UPSTREAM.git" ;;
esac
if [ -n "$LOGIN" ]; then
  perm="$(gh api "repos/$UPSTREAM" --jq '.permissions.push' 2>/dev/null)"
  [ "$perm" = "true" ] && aviso "sem escrita no time" "$LOGIN tem escrita no $UPSTREAM; o diretor trabalha sem (decisão de 24/11/2026)"
fi
email="$(git -C "$RAIZ" config user.email 2>/dev/null)"
case "$email" in
  *@users.noreply.github.com) ok "git config" "$(git -C "$RAIZ" config user.name)" ;;
  "") falta "git config" "git config --global user.name e user.email (o noreply do GitHub)" ;;
  *) aviso "git config" "e-mail pessoal vai para o repositório público; prefira o noreply do GitHub" ;;
esac

titulo "Parte 4. A cópia do app"
ENV="$APP/.env"
if [ -f "$ENV" ]; then
  if ! git -C "$RAIZ" check-ignore -q "$ENV"; then
    falta ".env local" "não está no .gitignore: não commite e avise o Pedro"
  elif grep -Eq 'https?://[a-z0-9.-]*hospitalsaomatheus\.cloud' "$ENV"; then
    falta ".env local" "cita endereço de produção: refaça com scripts/env_local.sh"
  else
    ok ".env local"
  fi
else
  falta ".env local" "bash .claude/skills/setup-diretor/scripts/env_local.sh (com o Supabase no ar)"
fi
if tem supabase && (cd "$APP" && supabase status >/dev/null 2>&1); then
  ok "Supabase local"
else
  falta "Supabase local" "cd hospital-reunioes && supabase start"
fi
curl -sf -o /dev/null --max-time 5 http://localhost:8000/api/health && ok "backend :8000" || falta "backend :8000" "skill atualizar-app --yes"
curl -sf -o /dev/null --max-time 5 http://localhost:3000 && ok "frontend :3000" || falta "frontend :3000" "skill atualizar-app --yes"

titulo "Parte 5. O Claude do jeito do time"
tem playwright-cli && ok "playwright-cli" || falta "playwright-cli" "npm install -g @playwright/cli@latest && playwright-cli install --skills"
SETTINGS="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json"
# A trava do merge (ADR 0113, decisão 2): o diretor é colaborador e o Claude dele
# nunca mergeia, nem pelo gh nem pela API. As regras são as do SKILL.md, Parte 5.
falta_trava=""
for regra in "Bash(gh pr merge:*)" "Bash(gh api *merge*)"; do
  if ! { [ -f "$SETTINGS" ] && tem jq && jq -e --arg r "$regra" '(.permissions.deny // []) | index($r)' "$SETTINGS" >/dev/null 2>&1; }; then
    falta_trava="$falta_trava $regra"
  fi
done
if [ -z "$falta_trava" ]; then
  ok "trava do merge"
else
  falta "trava do merge" "o settings.json do Claude não nega:$falta_trava (SKILL.md, Parte 5)"
fi
LISTA="$RAIZ/.claude/skills/setup-maquina/references/plugins.txt"
if [ -f "$LISTA" ]; then
  while IFS= read -r plugin; do
    [ -z "$plugin" ] && continue
    if [ -f "$SETTINGS" ] && tem jq && [ "$(jq -r --arg p "$plugin" '.enabledPlugins[$p] // false' "$SETTINGS")" = "true" ]; then
      ok "plugin ${plugin%%@*}"
    else
      falta "plugin ${plugin%%@*}" "claude plugin install $plugin"
    fi
  done < "$LISTA"
fi

printf '\n'
if [ "$FALHAS" -eq 0 ]; then
  echo "Tudo pronto: pode planejar com /grill-with-docs."
else
  echo "$FALHAS item(ns) faltando. Comece pelo primeiro FALTA."
  exit 1
fi
