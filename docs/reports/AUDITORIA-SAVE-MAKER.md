# Análise Técnica — Save Maker (performance, proposta e usabilidade)

**Data:** 2026-09-28 · **Branch:** `main` · **Commit base:** `0aa9f5f` (+ diff local não commitado em `scripts/core/mv_mz_adapter.py`)
**Escopo:** `main.py`, `scripts/core/*`, `scripts/ui/modern_app.py`, `scripts/cli/interactive.py`, `scripts/import_json_to_rpgsave.py`, `tests/*`

---

## 1. Sumário executivo

O Save Maker se apresenta como editor "universal, moderno e de alta performance" para saves de MV, MZ,
VX Ace, VX, XP, 2000/2003 e JSON (`README.md:7,13-20`). A interface cumpre boa parte do que promete: a
carga completa de um save MV real fica em ~0,37 s e as tabelas renderizam 778 linhas em ~7 ms. **Performance
não é o problema deste projeto.** O problema é que o núcleo de formatos **escreve saves corrompidos** em três
dos seis motores anunciados, e o fluxo de exportação/importação documentado no próprio README gera um save
que o jogo não consegue ler.

| # | Problema | Alcance | Severidade |
|---|---|---|---|
| U-01 | VX Ace/VX/XP: lê só o cabeçalho e **trunca** o arquivo ao salvar | Ruby (3 motores) | Crítica |
| U-02 | 2000/2003: chunks errados; ouro lido como 0 e gravado dentro de `pictures` | `.lsd` | Crítica |
| U-03 | `main.py export` → `main.py import` (README) produz save inválido | CLI, todos os JSON | Crítica |
| U-04 | Banco de dados de **outro jogo** carregado como *fallback* para qualquer save | Todos | Crítica |
| U-05 | Atributos de ator MV lidos como 0 e edições descartadas em silêncio | MV/MZ | Alta |
| U-07 | Fechar a janela descarta alterações sem aviso | GUI | Alta |
| P-01 | LZString em Python puro é ~97 % do tempo de carga | MV/MZ | Média |

**Veredicto:** interface bem cuidada e rápida o bastante; núcleo de formatos que só foi validado contra
fixtures escritas no formato que ele mesmo supõe, e que por isso corrompe saves reais fora do MV.

---

## 2. Metodologia e limites

### 2.1 O que foi feito

Leitura integral dos adaptadores, do gerenciador de banco de dados, da GUI moderna, da CLI e dos testes.
Reprodução em memória (ou em diretório temporário) de cada achado Crítico e Alto. Execução de `make test`.

**Protocolo de medição** (`medicao-desempenho.md` §2): notebook de 16 núcleos, Arch Linux (kernel 7.2.6),
Python 3.14.7 da `.venv`, sessão Wayland/XWayland · `time.perf_counter` em script inline (sem `hyperfine`
nem `py-spy` instalados — `which hyperfine py-spy` → não encontrado) · n = 10 com 2 execuções de aquecimento
descartadas para funções do núcleo; n = 12 processos novos, sem aquecimento, para a GUI · estado quente
(cache de disco aquecido) · estatística: mediana e máximo · ruído **não** controlado: governador de CPU,
*turbo boost*, outros processos da sessão. Entrada: `save/file2.rpgsave` — 118.129 B em disco, 515.239 B de
JSON após descompressão, compressão `none+lzstring`, 778 switches, 851 variáveis, 5 atores.

### 2.2 O que NÃO foi feito — limites desta análise

> Nenhum save editado foi aberto no jogo. Não havia no repositório save real de MZ, VX Ace, VX, XP ou
> 2000/2003; os achados U-01 e U-02 foram reproduzidos com arquivos sintéticos montados segundo a
> estrutura documentada nas fontes [F4], [F5] e [F6]. Não houve *profiling* por amostragem; a atribuição
> do custo ao LZString vem da decomposição por fase (seção 3.1), não de *flame graph*.

| Métrica | Limiar "Bom" | Fonte |
|---|---|---|
| Resposta a ação direta (editar célula, alternar switch) | ≤ 0,1 s | Nielsen [F7] |
| Operação sem perda de foco (abrir/salvar save) | ≤ 1 s | Nielsen [F7] |
| Limite para exigir barra de progresso e cancelamento | 10 s | Nielsen [F7] |

---

## 3. Evidências medidas

### 3.1 O LZString em Python puro é o gargalo da carga — e ele cabe no orçamento

| Fase (n = 10) | Mediana | Máx |
|---|---|---|
| `MvMzAdapter.load` total | 316,6 ms | 330,1 ms |
| `LZString.decompressFromBase64` | 318,2 ms | 351,4 ms |
| `_decompress` (5 tentativas de formato) | 4,7 ms | 5,7 ms |
| `json.loads` do payload | 3,5 ms | 4,9 ms |
| `LZString.compressToBase64` (caminho do *save*) | 125,8 ms | 136,6 ms |
| `GameDatabaseManager.discover_and_load` | 14,4 ms | 15,2 ms |

A descompressão LZString medida isoladamente tem a mesma ordem de grandeza da carga inteira: as demais
fases somam ~8 ms. O recurso limitante é **um núcleo de CPU executando bytecode Python** — o pacote
`lzstring` instalado é um único `__init__.py`, sem extensão C (`.venv/lib/python3.14/site-packages/lzstring/`).
Normalizado: ~0,6 ms de CPU por kB de JSON descomprimido. O dobro disso ainda ficaria abaixo de 1 s.

### 3.2 A GUI abre e carrega dentro do limite de 1 s

| Fase da GUI (n = 12, processos novos) | Mediana | Máx |
|---|---|---|
| Construção da janela (`ModernSaveEditorApp()` + `update`) | ~619 ms | 771 ms |
| `load_save_file(synchronous=True)` | ~373 ms | 436 ms |
| Render da aba Switches (778 linhas) | ~7 ms | 16 ms |

A carga real da GUI roda em *thread* (`modern_app.py:734-744`), então os ~0,37 s não bloqueiam a janela.

### 3.3 Verificação negativa: nem a Treeview nem a dupla carga do detector são gargalo

O README fala em "tabelas virtuais" (`README.md:28`); `ttk.Treeview` não é virtualizado — cada linha é um
item real (`modern_app.py:1305-1309`). Mesmo assim, 778 linhas custam ~7 ms, bem abaixo de 0,1 s. A dupla
carga do detector (P-03) custou 1,2 ms de mediana em `save/file2.json` (n = 10). As duas hipóteses de
gargalo estão refutadas para o tamanho de save medido e são registradas aqui para não voltarem a ser
levantadas.

### 3.4 A suíte passa, mas o `make test` é interrompido por um limiar de tempo

`make test` nesta sessão: `test_database_autodiscovery`, `test_all_formats` e `test_cli_interactive`
passaram; `test_performance` falhou em `test_performance.py:148` (`0.0114924400113523 not less than 0.01`) e o
`make` abortou antes de `test_editor.py` (`Makefile:135-141`). Rodado à parte, `test_editor.py` passou, e
`test_performance.py` passou 10 de 10 vezes em seguida. O limiar de 10 ms de relógio de parede é **instável**
e esconde o resultado dos testes seguintes.

---

## 4. Achados de performance

### P-01 · LZString em Python puro domina carga e gravação — **Média**

`scripts/core/mv_mz_adapter.py:41-48` + `:486-493`

```python
unb64 = _LZSTRING.decompressFromBase64(txt)   # linha 45 — 318 ms
...
comp = _LZSTRING.compressToBase64(txt)         # linha 490 — 126 ms
```

A implementação compara e concatena caracteres um a um em bytecode Python; o custo cresce linearmente com o
tamanho do JSON. Hoje fica dentro do limite de 1 s [F7], mas saves MV de jogos longos podem ser várias vezes
maiores que a amostra.

| Alcance | Impacto |
|---|---|
| GUI | Baixo — carga já roda em *thread*. |
| CLI / `export` | Médio — o terminal fica parado sem indicação além do *spinner*. |

**Custo [modelado]:** um save 5× maior → ~1,6 s de carga, acima do limite de 1 s.

**Reprodução:** medir `MvMzAdapter().load(Path("save/file2.rpgsave"))` com o protocolo da seção 2; a
decomposição da seção 3.1 mostra a fase LZString igual à carga total.

**Correção:** manter a carga fora da *thread* de UI (já feito em `modern_app.py:734-744`) e medir um save
grande antes de trocar a biblioteca; uma implementação nativa só entra com fonte que a sustente.
**Critério de aceite:** carga ≤ 1 s de mediana (n = 10, protocolo da seção 2) para um save MV de 500 kB em disco.

---

### P-02 · `_decompress` decodifica e varre o texto duas vezes — **Baixa**

`scripts/core/mv_mz_adapter.py:453-472` (diff local não commitado)

Os passos 4 e 5 repetem `data.decode("utf-8")` e `all(ord(c) <= 0xFF for c in txt)`; cada varredura custa
~2,3 ms na amostra (medido, n = 10). Em saves LZString o teste passa (Base64 é ASCII) e os dois `zlib`
falham, então o trabalho é sempre descartado.

**Reprodução:** chamar `MvMzAdapter()._decompress(Path("save/file2.rpgsave").read_bytes())` e medir: 4,7 ms,
metade gasta nas duas varreduras.

**Correção:** decodificar e testar uma vez, e tentar as duas variantes de `zlib` sobre o mesmo `raw`.
**Critério de aceite:** `_decompress` ≤ 2,5 ms de mediana na amostra, com os mesmos rótulos de compressão devolvidos.

---

### P-03 · Detector lê o arquivo inteiro por 16 bytes e carrega duas vezes — **Baixa**

`scripts/core/detector.py:31` + `:61-90`; chamadores em `modern_app.py:722-723`, `interactive.py:153-154`, `main.py:101-102`

`fpath.read_bytes()[:16]` lê o arquivo inteiro. Para `.json/.sav/.dat/.txt` e arquivos gzip/zlib sem
extensão conhecida, o detector já chama `adapter.load(fpath)` e todo chamador chama `load` de novo.

**Custo [modelado]:** um `.sav` que seja um MV LZString renomeado paga o LZString duas vezes (~0,64 s).

**Reprodução:** renomear uma cópia de `save/file2.rpgsave` para `.sav` e abrir pela GUI; o LZString roda nas
duas chamadas de `load`.

**Correção:** ler só o cabeçalho com `open(...).read(16)` e devolver do detector o adaptador já carregado,
sinalizando para o chamador não recarregar.
**Critério de aceite:** um contador em `MvMzAdapter.load` registra **uma** chamada ao abrir o `.sav` renomeado.

---

### P-04 · Lista de atores recriada a cada tecla da busca e a cada "Aplicar" — **Baixa**

`scripts/ui/modern_app.py:979-1015` + `:1036`

`_refresh_actors` destrói e recria um `CTkButton` por ator a cada busca (debounce de 150 ms) e a cada
aplicação de atributos. Com 5 atores o custo é imperceptível.

**Custo [modelado]:** jogos MV que tocam centenas de atores recriariam centenas de widgets CustomTkinter por tecla.

**Reprodução:** não disparado — a amostra tem 5 atores. Com um save de 200 atores, digitar na busca global
na aba Personagens e observar o atraso.

**Correção:** atualizar só o botão alterado em "Aplicar", como a edição de célula já faz em `:1162-1180`.
**Critério de aceite:** "Aplicar" não chama `winfo_children()`/`destroy()`; asserção em teste com *mock*.

---

## 5. Achados de usabilidade e correção

### U-01 · VX Ace/VX/XP: lê só o cabeçalho e trunca o save ao gravar — **Crítica**

`scripts/core/ruby_adapter.py:44-45` + `:70-71`

```python
with open(self.file_path, "rb") as fd:
    self.raw_data = ruby_load(fd)        # linha 45 — lê UM objeto Marshal
...
    ruby_write(fd, self.raw_data)        # linha 71 — grava UM objeto
```

O VX Ace grava dois objetos em sequência — `Marshal.dump(make_save_header, file)` e
`Marshal.dump(make_save_contents, file)` [F4]; o XP grava doze (`characters`, `frame_count`, `$game_system`,
…) [F5]. O adaptador lê só o primeiro, não encontra `Game_Party` (fica em `contents[:party]`) e, ao salvar,
regrava só o cabeçalho: **todo o estado do jogo é apagado**, protegido apenas pelo `.bak` único (U-08).

**Reprodução:** executado nesta sessão — blob `writes(header) + writes({:party => Game_Party(@gold=1500)})`
de 82 B salvo como `Save01.rvdata2`; `RubyAdapter.load` devolve `get_gold() == 0` e `game_party_obj is None`;
`save` grava 46 B.

**Correção:** ler objetos em laço até EOF, localizar os objetos RGSS em todos eles e regravar a lista inteira
na mesma ordem. O teste precisa usar o formato de [F4] e não a lista única de `test_all_formats.py:127-128`.
**Critério de aceite:** teste com o blob de dois objetos acima: `get_gold() == 1500`, e após `save` o arquivo
relido tem dois objetos, o segundo com `@gold` alterado.

---

### U-02 · 2000/2003: chunks errados, ouro lido como 0 e gravado em `pictures` — **Crítica**

`scripts/core/lsd_adapter.py:101` + `:109` + `:130` + `:186-213`

O adaptador procura o ouro nos chunks `103/104` (`0x67`/`0x68`). Na especificação do liblcf, `0x67` é
`pictures` e `0x68` é `party_location`; o ouro fica em `inventory` (`0x6D`), campo `0x15`, e os IDs de item
em `0x0C`, não `0x0B` [F6]. Switches (`0x20`) e variáveis (`0x22`) de `SaveSystem` nunca são lidos, então as
abas ficam vazias. `get_actors` devolve quatro heróis fictícios com HP 999 (`:186-209`) e `update_actor` só
marca o save como alterado sem mudar nada (`:211-213`) — o usuário "edita" e nada acontece.

**Reprodução:** executado nesta sessão — `.lsd` sintético com chunk `0x67` arbitrário e ouro em
`0x6D/0x15`: `get_gold()` devolve 0; após `set_gold(99999)` e `save`, o arquivo cresce 7 B dentro do chunk
`0x67` e o `0x6D` fica intacto.

**Correção:** mapear `0x6D`/`0x15` (ouro), `0x0C`/`0x0D` (itens) e `0x65`/`0x20`/`0x22` segundo [F6]; até
lá, abrir `.lsd` em modo somente leitura e retirar 2000/2003 da lista de suporte do README.
**Critério de aceite:** teste com o `.lsd` sintético acima: `get_gold() == 2500` e, após `save`, só o campo
`0x15` de `0x6D` muda — o chunk `0x67` é idêntico byte a byte.

---

### U-03 · O round-trip `export` → `import` do README gera save inválido — **Crítica**

`main.py:105-110` × `scripts/import_json_to_rpgsave.py:69-88`

```python
out = {"engine": ..., "compression": ..., "data": adapter.raw_data}   # main.py:105-109 — sem "format"
...
else:
    payload = json.dumps(js, ensure_ascii=False).encode("utf-8")      # import:86-88 — o wrapper inteiro
```

O `export` de `main.py` (e o da GUI em `modern_app.py:1561-1566` e o da CLI em `interactive.py:468-473`)
não grava a chave `format`. O importador, sem `format`, trata o JSON inteiro como payload: o save gerado
tem na raiz `engine`, `compression` e `data`, em vez de `system`, `party`, `actors`. É exatamente o fluxo
ensinado em `README.md:86-89`.

**Reprodução:** executado nesta sessão — `main.py export save/file2.rpgsave e.json` seguido de
`main.py import e.json r.rpgsave`; as chaves da raiz de `r.rpgsave` descomprimido são
`['engine', 'compression', 'data']`.

**Correção:** um único formato de exportação para os três pontos, reaproveitando `MvMzAdapter.export_to_json`
(`mv_mz_adapter.py:96-106`), e o importador desembrulhar `data` sempre que ela existir.
**Critério de aceite:** teste de subprocesso `export` → `import` → `export` em que o `data` final é igual ao
inicial e a raiz do save reimportado contém `party`.

---

### U-04 · Banco de dados de outro jogo carregado para qualquer save — **Crítica**

`scripts/core/database_manager.py:100-103` + `:105-110`

```python
root_dir = Path(__file__).resolve().parent.parent.parent
candidate_dirs.append(root_dir / "save" / "data")    # linha 102 — dados versionados de UM jogo
```

Quando a pasta do jogo não é achada, o gerenciador carrega `save/data/` do próprio repositório — os dados
de um jogo específico (ator 1 "Himeno Iroha", switches em japonês). Todo save de qualquer outro jogo passa a
exibir nomes errados, e "Desbloquear Todos os Itens" (`mv_mz_adapter.py:289-298`) **injeta 390 IDs de item
de outro jogo** no inventário. Além disso, o `GLOBAL_DB` só é limpo quando uma pasta é encontrada
(`:105-110` → `load_directory` → `clear`), então sem o *fallback* os nomes do save anterior vazariam para o
seguinte.

**Reprodução:** executado nesta sessão — `GameDatabaseManager().discover_and_load(<pasta vazia>/x.rvdata2)`
devolve `True` com `data_dir = <repo>/save/data`. Pela GUI: abrir qualquer save fora de uma pasta de jogo; o
rodapé mostra "BD: Conectado (390 itens, …)".

**Correção:** remover os dois candidatos do repositório; chamar `self.clear()` no início de
`discover_and_load`; mover a amostra de teste para `tests/fixtures/`, passada explicitamente aos testes.
**Critério de aceite:** `discover_and_load` numa pasta sem `data/` devolve `False` e `is_loaded()` é `False`,
mesmo depois de um carregamento bem-sucedido anterior na mesma instância.

---

### U-05 · Atributos de ator MV lidos como 0 e edições descartadas — **Alta**

`scripts/core/mv_mz_adapter.py:176-180` + `:188` + `:219-222`

No save real, `_paramPlus` vem embrulhado pelo `JsonEx`: `{"@c": 104, "@a": [50, 50, 0, …]}` — o `JsonEx`
converte todo array em objeto com `@a` [F1]. O adaptador só aceita `list`, troca o valor por `[0]*8` na
leitura e, na escrita, grava chaves `"0"`, `"2"` ao lado de `@a` — que o decodificador descarta [F1]. Pior:
`_paramPlus` é um **bônus** somado ao parâmetro da classe, não o valor máximo [F3], e `max_hp` cai para o HP
atual quando o bônus é 0 (`:188`). Por isso "Curar Todo o Grupo" define HP = HP atual e não cura ninguém.

**Reprodução:** executado nesta sessão — no `save/file2.rpgsave`, `update_actor(1, {"atk": 999, "max_hp": 9999})`
deixa `_paramPlus = {"@c":104,"@a":[50,50,0,0,0,0,0,0],"0":9999,"2":999}` e a releitura mostra `atk 0`, `max_hp 211`.

**Correção:** desembrulhar `@a` como `get_switches` já faz (`mv_mz_adapter.py:315-317`) e rotular os campos
como "bônus"; o máximo real exige `Classes.json` (`params[paramId][level]`, [F2]), já carregado pelo BD.
**Critério de aceite:** teste no save real: após `update_actor(1, {"atk": 999})`, `raw["_paramPlus"]["@a"][2] == 999`
e não existe chave numérica fora de `@a`.

---

### U-06 · Nível editado sem experiência volta ao valor anterior no jogo — **Alta**

`scripts/core/mv_mz_adapter.py:198` + `:208-209`

O editor muda `_level` e deixa `_exp[classId]` intacto. No MV, `changeExp` corrige o nível até ficar
coerente com a experiência: `while (this.currentExp() < this.currentLevelExp()) this.levelDown();` [F2]. O
primeiro ganho de experiência desfaz os "+5 níveis" e o "nível 99". A leitura de `exp` usa a chave fixa `"1"`
(`:198`), errada para qualquer ator cuja classe não seja 1 — o `_exp` é indexado por `_classId` [F2].

**Reprodução:** pela leitura do código e de [F2]; não executado no jogo. Subir o ator 1 para o nível 99,
salvar, abrir no jogo e vencer uma batalha: o nível volta a 1.

**Correção:** ao mudar o nível, gravar `_exp[_classId] = expForLevel(level)` com a curva de `Classes.json`,
como faz `changeLevel` [F2].
**Critério de aceite:** teste: após `update_actor(1, {"level": 10})`, `_exp[str(_classId)]` é igual à
experiência mínima do nível 10 calculada da curva da classe.

---

### U-07 · Fechar a janela descarta alterações sem aviso — **Alta**

`scripts/ui/modern_app.py:62-116` (construtor sem *handler* de fechamento)

```bash
grep -rn "WM_DELETE_WINDOW\|protocol(" scripts/ main.py
# → 0 resultados
```

A GUI mostra "N alterações não salvas" (`:828-840`) mas o botão de fechar da janela encerra o processo sem
perguntar. A CLI já tem o comportamento certo (`interactive.py:214-217`).

**Reprodução:** abrir um save, clicar "+10.000" de ouro e fechar a janela: nenhuma pergunta, alteração perdida.

**Correção:** `self.protocol("WM_DELETE_WINDOW", …)` com `messagebox.askyesnocancel` quando `adapter.dirty`,
espelhando `interactive.py:214-217`.
**Critério de aceite:** teste de GUI com `messagebox` substituído por *mock*: com `dirty=True`, o *handler*
pergunta e não chama `destroy` quando a resposta é "Cancelar".

---

### U-08 · Backup único sobrescrito, escrita não atômica e aviso falso — **Alta**

`scripts/core/base_adapter.py:57-64` + `mv_mz_adapter.py:92` + `modern_app.py:1538,1575`

Cada "Salvar" copia o arquivo atual para `<nome>.bak`: no segundo "Salvar" da sessão, o original some e o
`.bak` passa a conter a primeira versão editada. Se a cópia falha, o erro é só impresso (`:63-64`) e o save
é sobrescrito assim mesmo. A escrita é direta (`dst_path.write_bytes`), sem arquivo temporário:

```bash
grep -rn "os.replace\|fsync\|NamedTemporaryFile" scripts/
# → 0 resultados
```

"Salvar como" chama `save(p, backup=False)` (`modern_app.py:1538`), mas o diálogo de sucesso afirma "Um
backup (.bak) de segurança foi gerado" (`:1575`). Com U-01 e U-02 corrompendo saves, o backup é a única rede
de proteção — e ela protege uma gravação só.

**Reprodução:** abrir `file.rpgsave`, alterar o ouro, salvar; alterar de novo, salvar; `file.rpgsave.bak` já
não é o original.

**Correção:** backup do original uma vez por sessão (ou `.bak` com carimbo de hora), abortar o save se o
backup falhar, gravar em temporário + `os.replace`, e condicionar a mensagem a `backup=True`.
**Critério de aceite:** teste: dois `save()` seguidos mantêm no `.bak` os bytes do arquivo original; com
`shutil.copy2` forçado a falhar, `save()` levanta exceção e o destino não muda.

---

### U-09 · Gravação em *thread* concorre com edições na UI — **Média**

`scripts/ui/modern_app.py:1512-1520`

`save_current_file` serializa `adapter.raw_data` numa *thread* (LZString ~126 ms, seção 3.1) enquanto os
botões continuam ativos e mutam o mesmo dicionário. Uma edição durante a gravação pode sair meio aplicada ou
disparar `RuntimeError: dictionary changed size during iteration`; `clear_pending_changes` ao fim
(`mv_mz_adapter.py:93`) ainda apaga o indicador de uma alteração que não foi gravada.

**Reprodução:** só pela leitura do código; não disparado. Com um save grande, clicar "Salvar" e em seguida
"Desbloquear Todas as Armaduras".

**Correção:** serializar `json.dumps` na *thread* de UI (≈ 4 ms, seção 3.1) e deixar só compressão e escrita
na *thread*; ou desabilitar as ações até o fim da gravação.
**Critério de aceite:** teste que muta `raw_data` durante `save()` com *patch* de atraso e verifica que o
arquivo corresponde ao instantâneo e que `dirty` continua `True`.

---

### U-10 · Entradas inválidas são rejeitadas em silêncio — **Média**

`scripts/ui/modern_app.py:1031-1034` + `:1148-1149`

"Aplicar ao Personagem" só aceita campos em que `txt.isdigit()`: `-5`, `1.000` ou espaço no meio são
ignorados sem aviso, e a mensagem de status diz "salvos" (`:1038`). A quantidade de item faz o mesmo.
O campo de ouro, ao contrário, mostra `messagebox` de valor inválido (`:886-887`) — o precedente certo.

**Reprodução:** digitar `1.000` em ATK, clicar "Aplicar": status "Atributos … salvos!" e ATK inalterado.

**Correção:** validar como `_apply_gold_from_entry` (`:879-887`) e marcar o campo inválido.
**Critério de aceite:** teste de GUI: ATK = `abc` → `messagebox.showwarning` chamado e `update_actor` não chamado.

---

### U-11 · Árvore avançada corta em 200 filhos sem aviso — **Média**

`scripts/ui/modern_app.py:1452,1455`

`list(container.items())[:200]` e `container[:200]` truncam qualquer nó. O save de amostra tem 851 variáveis
e 778 switches: 651 variáveis ficam inalcançáveis justamente na aba vendida como "Árvore Completa (JSON Raw)"
(`README.md:27`), sem indicação de que há mais.

**Reprodução:** aba "Modo Avançado", expandir `variables → _data → @a`: o último índice exibido é 199.

**Correção:** inserir um nó "… mais N itens" que carrega o próximo lote ao ser expandido.
**Critério de aceite:** teste de GUI: expandir `@a` e o nó de continuação até o fim resulta em 852 filhos.

---

### U-12 · JSON genérico: armas e armaduras tratadas como itens — **Média**

`scripts/core/generic_adapter.py:139` + `:156-168`

`get_inventory` nomeia qualquer tipo com `db.get_item_name` (`:139`); `unlock_all_items` preenche armas e
armaduras com a lista de **itens** (`:161`) e não chama `mark_dirty` — a alteração não aparece no indicador e
a CLI não pergunta antes de sair.

**Reprodução:** abrir `{"weapons": {}}` como `.json` com BD carregado e clicar "Desbloquear Todas as Armas":
o inventário de armas recebe os IDs de itens e o indicador continua "Salvo".

**Correção:** selecionar a fonte pelo `kind`, como `MvMzAdapter.unlock_all_items` (`mv_mz_adapter.py:289-293`), e marcar sujo.
**Critério de aceite:** teste: após `unlock_all_items("weapons")`, as chaves são as de `db.weapons` e `dirty is True`.

---

### U-13 · CLI esconde linhas além de 50/100 com rótulo enganoso — **Baixa**

`scripts/cli/interactive.py:375,380` + `:412,417`

A tabela de switches imprime `filtered[:50]` com o título "Switches (778 exibidos)"; o inventário corta em 100.
O usuário acredita estar vendo tudo.

**Reprodução:** menu 6 sem filtro: título "778 exibidos", 50 linhas impressas.

**Correção:** título "50 de 778 — use o filtro" quando houver corte.
**Critério de aceite:** teste com `Console(record=True)` verifica "50 de 778" na saída.

---

## 6. Observação estrutural: promessa do README × realidade

| Promessa (`README.md`) | Estado verificado | Status |
|---|---|---|
| MV `.rpgsave` (`:14`) | Único formato com amostra real; round-trip do adaptador passa | ✅ |
| MZ `.rmmzsave` (`:15`) | Suporte `zlib-utf8` só no diff local; `grep -rn "zlib-utf8" tests/` → 0 resultados | 🟡 |
| VX Ace / VX / XP (`:16-18`) | Lê só o primeiro objeto Marshal e trunca ao salvar (U-01) | ❌ |
| 2000/2003 `.lsd` (`:19`) | Chunks errados, atores fictícios, switches vazios (U-02) | ❌ |
| JSON / Web (`:20`) | Ouro e switches funcionam; armas/armaduras erradas (U-12) | 🟡 |
| Nomes reais do BD (`:21-23`) | Funciona dentro da pasta do jogo; fora dela, BD de outro jogo (U-04) | ⚠️ |
| "Tabelas virtuais", "< 0.1ms" (`:28`) | `ttk.Treeview` comum; teste exige < 10 ms (`test_performance.py:130`) | ⚠️ |
| Export/Import (`:84-90`) | Round-trip gera save inválido (U-03) | ❌ |

A distância entre promessa e entrega está concentrada no núcleo, não na interface. A recomendação é reduzir
o README ao que é verificado (MV e JSON) e reintroduzir cada motor junto com um save real de teste.

---

## 7. Achado transversal: os testes validam o formato que o próprio código supõe

Os testes de formato montam fixtures com a mesma suposição que o adaptador faz: o save Ruby é **uma lista
única** de objetos (`tests/test_all_formats.py:127-128`) e o `.lsd` coloca o ouro no chunk `104`
(`:177-180`). O round-trip passa porque escreve e lê o mesmo erro; U-01 e U-02 ficam invisíveis. O mesmo
vale para `test_editor.py:101-121`, que testa uma cópia local de `get_by_path`/`set_by_path` e não o código de
`base_adapter.py:166-209`.

Não há executor de testes nem integração contínua:

```bash
ls .github pyproject.toml pytest.ini setup.cfg
# → No such file or directory (4 de 4)
```

`make test` roda cinco scripts em sequência e para no primeiro erro (`Makefile:135-141`), e um limiar de
relógio de 10 ms já interrompeu a suíte nesta sessão (seção 3.4). Recomendação: fixtures geradas a partir
das fontes oficiais [F4] [F5] [F6] (ou saves reais de projetos-exemplo) em `tests/fixtures/`, `pytest` como
executor único, e limiares de tempo como métricas relatadas, não como asserções que derrubam a suíte.

---

## 8. O que está bem feito

| Local | Decisão |
|---|---|
| `modern_app.py:776-826` | Abas com atualização preguiçosa: só a aba visível é redesenhada |
| `modern_app.py:1489-1493` | Busca global com *debounce* de 150 ms |
| `modern_app.py:118-132,734-744` | Carga em *thread* com fila para a *thread* de UI — correto para Tkinter |
| `modern_app.py:1162-1180` | Edição de quantidade altera a célula sem redesenhar a tabela |
| `database_manager.py:81-98` | Descoberta por lista de pastas candidatas (`data`, `www/data`, pais) |
| `base_adapter.py:33-43` | *Dirty tracking* com contagem de alterações, usado na GUI e na CLI |
| `interactive.py:214-217` | CLI pergunta antes de sair com alterações pendentes |

---

## 9. Backlog priorizado

> Ordenado por (impacto no usuário × alcance) ÷ esforço.

| Pri | Item | Esforço | Alcance | Tipo |
|---|---|---|---|---|
| 1 | **U-04** — remover *fallback* do BD e limpar no início | XS | Todos | Correção |
| 2 | **U-07** — confirmar ao fechar com alterações | XS | GUI | UX |
| 3 | **U-08** — backup do original, escrita atômica, mensagem correta | S | Todos | Correção |
| 4 | **U-03** — formato único de exportação e importador que desembrulha | S | CLI/GUI | Correção |
| 5 | **U-01** — Marshal com múltiplos objetos + fixture real | S | VX Ace/VX/XP | Correção |
| 6 | **U-02** — `.lsd` em somente leitura e fora do README; depois mapear [F6] | S / L | 2000/2003 | Correção |
| 7 | **U-05 + U-06** — atributos e nível MV com `Classes.json` | M | MV/MZ | Correção |
| 8 | Achado transversal — fixtures reais, `pytest`, limiares não bloqueantes | M | Todos | Qualidade |
| 9 | **U-09 + U-10 + U-11 + U-12 + U-13** | S | Vários | UX |
| 10 | **P-01 a P-04** | XS–S | MV/MZ | Perf |

U-05 e U-06 são uma unidade: os dois dependem da curva de parâmetros e de experiência de `Classes.json` e
mexem no mesmo `update_actor`. U-02 aparece com dois esforços porque a mitigação (somente leitura) é S e a
implementação completa do LCF é L.

Os itens 1 e 2 somam menos de uma hora de trabalho e fecham as duas formas mais silenciosas de perder dados
(nomes e itens de outro jogo; alteração descartada ao fechar). Os itens de performance ficam por último e
devem ser aplicados um por vez, medindo de novo com o protocolo da seção 2 entre eles.

---

## 10. Riscos e o que falta verificar

1. **Nenhum save editado foi aberto no jogo.** Antes de declarar U-01, U-02, U-05 e U-06 resolvidos, abrir
   no motor real um save de cada formato editado pela ferramenta e conferir ouro, nível após uma batalha e
   inventário.
2. **O formato `zlib-utf8` do MZ não tem fonte nesta análise.** O diff local afirma que o MZ grava o fluxo
   zlib como texto UTF-8; isso não foi conferido, e o importador trata `zlib-utf8` como `zlib` comum
   (`import_json_to_rpgsave.py:52-53`), o que produziria um `.rmmzsave` diferente do lido. Precisa de um save
   MZ real e da fonte do `StorageManager` do MZ.
3. **A codificação dos inteiros no LCF não foi confirmada.** A tabela de campos [F6] foi lida; o código de
   leitura do liblcf não pôde ser aberto (404). O critério de U-02 assume `Int32` codificado como inteiro BER.
4. **`save/data/` versiona ~14 MB de dados de um jogo comercial** (`Animations.json` sozinho tem 11,9 MB), e
   `exemple/` e `save/` trazem saves desse jogo. A licença desses arquivos não foi verificada; além do risco
   legal, são eles que alimentam U-04.
5. **Números de uma máquina só.** Todos os tempos vêm de um notebook de 16 núcleos com ruído não controlado;
   em máquinas modestas P-01 pode passar de 1 s antes do previsto.
6. **U-09 não foi disparado.** A concorrência vem da leitura do código; a correção é barata e correta
   independentemente de reprodução.

---

## 11. Fontes consultadas

| # | Fonte | Tipo | Versão | Consultada em | Sustenta |
|---|---|---|---|---|---|
| F1 | [`rpgtkoolmv/corescript` — `js/rpg_core/JsonEx.js`](https://github.com/rpgtkoolmv/corescript/blob/master/js/rpg_core/JsonEx.js) | Exemplo do mantenedor | `master` (MV) | 2026-09-28 | U-05 |
| F2 | [`rpgtkoolmv/corescript` — `js/rpg_objects/Game_Actor.js`](https://github.com/rpgtkoolmv/corescript/blob/master/js/rpg_objects/Game_Actor.js) | Exemplo do mantenedor | `master` (MV) | 2026-09-28 | U-05, U-06 |
| F3 | [`rpgtkoolmv/corescript` — `js/rpg_objects/Game_BattlerBase.js`](https://github.com/rpgtkoolmv/corescript/blob/master/js/rpg_objects/Game_BattlerBase.js) | Exemplo do mantenedor | `master` (MV) | 2026-09-28 | U-05 |
| F4 | [`orzFly/RPGMakerDefaultScripts` — VX Ace `DataManager.rb`](https://github.com/orzFly/RPGMakerDefaultScripts/blob/master/rpgmaker-vxace.en/DataManager.rb) | Projeto de terceiros | `master` | 2026-09-28 | U-01 |
| F5 | [`orzFly/RPGMakerDefaultScripts` — XP `Scene_Save.rb`](https://github.com/orzFly/RPGMakerDefaultScripts/blob/master/rpgmaker-xp.en/Scene_Save.rb) | Projeto de terceiros | `master` | 2026-09-28 | U-01 |
| F6 | [`EasyRPG/liblcf` — `generator/csv/fields.csv`](https://github.com/EasyRPG/liblcf/blob/master/generator/csv/fields.csv) | Projeto de terceiros | `master` | 2026-09-28 | U-02 |
| F7 | [Nielsen — *Response Times: The 3 Important Limits*](https://www.nngroup.com/articles/response-times-3-important-limits/) | Artigo | — | 2026-09-28 | Limiares da seção 2 |

Não puderam ser consultadas: a página do `lzstring` no PyPI (não carregou) e `src/reader_struct.cpp` do
liblcf (404). A ausência de extensão C no `lzstring` vem da inspeção do pacote instalado, não da documentação.
F4 e F5 são espelhos comunitários dos scripts padrão do RPG Maker, não a distribuição oficial. F7 é artigo,
usado só como referência de limiar de percepção, não para sustentar correção.

---

> Nenhum item deste relatório foi executado dentro de um jogo RPG Maker. A análise vem da leitura do código
> no branch `main` (commit `0aa9f5f`, mais o diff local em `mv_mz_adapter.py`), de medições locais com o
> protocolo da seção 2 e de reproduções com o save MV de amostra e arquivos sintéticos de VX Ace e 2000/2003;
> a validação com saves reais está pendente na seção 10.
