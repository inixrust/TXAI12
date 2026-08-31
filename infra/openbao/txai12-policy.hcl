# Kebijakan BACA-SAJA untuk aplikasi TX-AI12.
# Aplikasi hanya boleh MEMBACA rahasianya sendiri di secret/txai12 - tak boleh
# menulis, dan tak boleh menyentuh rahasia lain. Token app dibuat dengan
# kebijakan ini (lihat bootstrap.sh), berumur pendek dan dapat diperbarui.
path "secret/data/txai12" {
  capabilities = ["read"]
}
path "secret/metadata/txai12" {
  capabilities = ["read"]
}
