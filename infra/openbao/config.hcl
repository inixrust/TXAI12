# Konfigurasi OpenBao untuk TX-AI12 - server produksi-ringan (BUKAN dev mode).
#
# Dev mode (`bao server -dev`) menyimpan rahasia DI MEMORI dan auto-unseal dengan
# root token tetap - nyaman untuk coba-coba, TAPI semua hilang saat restart dan
# tak ada segel. Untuk apa pun yang menyimpan rahasia sungguhan, pakai storage
# persisten + unseal sungguhan seperti di bawah.
storage "file" {
  path = "/openbao/data"
}

listener "tcp" {
  address = "0.0.0.0:8200"
  # TLS diterminasi oleh Caddy di depan, dan jaringan 'backend' bersifat
  # internal (tanpa rute ke luar). Untuk deployment di mana OpenBao terekspos
  # langsung, AKTIFKAN TLS di sini (tls_cert_file/tls_key_file) - jangan
  # mengandalkan proxy saja.
  tls_disable = true
}

# UI web OpenBao (opsional) - berguna saat bootstrap. Aman dimatikan setelahnya.
ui = true

# CATATAN SEGEL (seal/unseal): setelah `bao operator init`, OpenBao mulai dalam
# keadaan SEALED dan TIDAK bisa membaca rahasia sampai di-unseal dengan ambang
# kunci Shamir (mis. 3 dari 5). Setiap restart container -> tersegel lagi ->
# app tak dapat rahasia sampai operator unseal. Untuk single-node tanpa jaga
# 24 jam, pertimbangkan auto-unseal (transit/cloud KMS). Ini konsekuensi
# operasional, bukan bug - lihat infra/README.md.
