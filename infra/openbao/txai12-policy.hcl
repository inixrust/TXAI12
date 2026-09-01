# Kebijakan BACA-SAJA untuk aplikasi TX-AI12.
# Aplikasi hanya boleh MEMBACA rahasianya sendiri di secret/txai12 - tak boleh
# menulis, dan tak boleh menyentuh rahasia lain. Token app dibuat dengan
# kebijakan ini (lihat bootstrap.sh), berumur pendek dan dapat diperbarui.
# txai12       : rahasia untuk app di HOST (alamat DB localhost:6024/1521).
# txai12-app   : rahasia untuk app DI CONTAINER (alamat DB pakai nama container
#                pg-txai12:5432 / oracle-txai12:1521 di jaringan Docker).
path "secret/data/txai12" {
  capabilities = ["read"]
}
path "secret/metadata/txai12" {
  capabilities = ["read"]
}
path "secret/data/txai12-app" {
  capabilities = ["read"]
}
path "secret/metadata/txai12-app" {
  capabilities = ["read"]
}

# Kredensial DB DINAMIS (efemeral) - app meminta user/sandi berumur pendek
# alih-alih memakai sandi statis. Peran dinamis anggota rag_app, jadi RLS tetap.
path "database/creds/rag_app_dyn" {
  capabilities = ["read"]
}
