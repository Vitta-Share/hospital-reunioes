#!/usr/bin/env bash
# Grava o hospital-reunioes/.env do diretor só com valores do Supabase local.
#
# Parte do .env.example, põe as duas chaves que o `supabase status` dá (anon e
# service_role do banco local) e esvazia todo <PREENCHER> que sobrar: chave de IA,
# de e-mail e de assinatura vazias ligam o modo simulado do app, sem custo e sem
# tocar serviço de fora. Nunca imprime valor de chave e nunca sobrescreve um .env
# existente. Uso: bash env_local.sh
set -euo pipefail

raiz=$(git rev-parse --show-toplevel)
app="$raiz/hospital-reunioes"
modelo="$app/.env.example"
destino="$app/.env"

[ -f "$modelo" ] || { echo "FALTA: $modelo não existe. Rode dentro do clone do hospital-reunioes."; exit 1; }
command -v supabase >/dev/null || { echo "FALTA: Supabase CLI. brew install supabase/tap/supabase"; exit 1; }

status=$(cd "$app" && supabase status -o env 2>/dev/null) || {
  echo "FALTA: o Supabase local não está no ar. cd hospital-reunioes && supabase start"
  exit 1
}

valor() { printf '%s\n' "$status" | awk -F= -v k="$1" '$1 == k { sub(/^[^=]*=/, ""); gsub(/^"|"$/, ""); print; exit }'; }
anon=$(valor ANON_KEY)
service=$(valor SERVICE_ROLE_KEY)
[ -n "$anon" ] && [ -n "$service" ] || {
  echo "FALTA: o supabase status não trouxe ANON_KEY e SERVICE_ROLE_KEY. Versão do CLI: $(supabase --version)"
  exit 1
}

if [ -f "$destino" ]; then
  echo "AVISO: $destino já existe e não foi tocado. Para refazer, renomeie para .env.local (o git ignora) e rode de novo."
  exit 0
fi
alvo="$destino"

ANON="$anon" SERVICE="$service" awk '
  /^SUPABASE_SERVICE_ROLE_KEY=/     { print "SUPABASE_SERVICE_ROLE_KEY=" ENVIRON["SERVICE"]; next }
  /^NEXT_PUBLIC_SUPABASE_ANON_KEY=/ { print "NEXT_PUBLIC_SUPABASE_ANON_KEY=" ENVIRON["ANON"]; next }
  /=<PREENCHER>/                    { sub(/=<PREENCHER>.*/, "="); print; next }
  { print }
' "$modelo" > "$alvo"
chmod 600 "$alvo"

if ! git -C "$raiz" check-ignore -q "$alvo"; then
  echo "PARE: $alvo não está no .gitignore. Não commite e avise o Pedro."
  exit 1
fi

if grep -Eq 'https?://[a-z0-9.-]*hospitalsaomatheus\.cloud' "$alvo"; then
  echo "PARE: $alvo cita endereço de produção. Apague a linha e avise o Pedro."
  exit 1
fi

echo "OK: $alvo gravado com as chaves do Supabase local (valores não impressos). IA, e-mail e assinatura no modo simulado."
