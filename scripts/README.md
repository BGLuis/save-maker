# scripts: export/import .rpgsave <-> JSON

Arquivos:

- `export_rpgsave_to_json.py` : Lê um `.rpgsave`, detecta compressão (gzip/zlib/none), tenta parsear JSON e exporta um JSON de metadados. Se o payload não for JSON, salva o conteúdo bruto em base64.
- `import_json_to_rpgsave.py` : Lê o JSON produzido pelo exportador e reconstrói o `.rpgsave`, preservando a compressão original ou usando a compressão fornecida via `--compression`.

Exemplos:

```bash
python scripts/export_rpgsave_to_json.py export save/file2.rpgsave save/file2.json
python scripts/import_json_to_rpgsave.py import save/file2.json save/file2_new.rpgsave
```

Observações:
- O exportador tenta detectar JSON interno e decodificá-lo. Se o conteúdo for binário, use o campo `raw_base64` do JSON.
- O importador cria um backup do destino se o arquivo já existir (sufixo `.bak`).
- Esses scripts usam apenas bibliotecas padrão do Python.
