#!/usr/bin/env python3
"""
GUI simples para manipular .rpgsave / .rmmzsave <-> JSON usando tkinter

Funcionalidades:
- Suporte a RPG Maker MV (.rpgsave) e MZ (.rmmzsave)
- Thread-safe (usa Queue para evitar congelamentos/crashes)
- Drag & Drop
"""

import sys
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
import json
import queue  # Importante para thread safety

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPTS_DIR.parent
for d in (str(SCRIPTS_DIR), str(ROOT_DIR)):
    if d not in sys.path:
        sys.path.insert(0, d)

try:
    from export_rpgsave_to_json import export_rpgsave
except Exception:
    export_rpgsave = None

try:
    from import_json_to_rpgsave import import_json
except Exception:
    import_json = None

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _DND_AVAILABLE = True
except Exception:
    TkinterDnD = None
    DND_FILES = None
    _DND_AVAILABLE = False


BaseApp = TkinterDnD.Tk if _DND_AVAILABLE else tk.Tk

# Definição de extensões suportadas
RPGSAVE_EXTS = ('*.rpgsave', '*.rmmzsave')
RPGSAVE_TUPLE = ('.rpgsave', '.rmmzsave')

class App(BaseApp):
    def __init__(self):
        super().__init__()
        self.title('RPG Maker Save Editor (MV/MZ)')
        self.geometry('1000x680')

        # Fila para comunicação Thread -> GUI (Thread Safety)
        self.gui_queue = queue.Queue()

        self.create_widgets()
        if _DND_AVAILABLE:
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind('<<Drop>>', self.on_drop)
            except Exception:
                pass
        else:
            # fallback on_drop stub
            App.on_drop = lambda s, e: None

        # Inicia loop de verificação da fila
        self.check_queue()

    def check_queue(self):
        """Verifica se há tarefas de UI pendentes na fila."""
        try:
            while True:
                task = self.gui_queue.get_nowait()
                func, args, kwargs = task
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    print(f"Erro na atualização de UI: {e}")
        except queue.Empty:
            pass
        finally:
            self.after(100, self.check_queue)

    def queue_ui(self, func, *args, **kwargs):
        """Enfileira uma função de UI para ser executada na Main Thread."""
        self.gui_queue.put((func, args, kwargs))

    def create_widgets(self):
        frm = ttk.Frame(self)
        frm.pack(fill='both', expand=True, padx=8, pady=8)

        # Style tweaks
        try:
            style = ttk.Style()
            try:
                style.theme_use('clam')
            except Exception:
                pass
            style.configure('Header.TLabel', font=('TkDefaultFont', 10, 'bold'))
            style.configure('TButton', padding=(6, 4))
            style.configure('Small.TButton', padding=(4,3), font=('TkDefaultFont', 9))
            style.configure('Alert.TButton', background='#ffef99')
            style.map('Alert.TButton', background=[('active', '#ffe680')])
            style.configure('Status.Highlight.TLabel', background='#fff3b0')
        except Exception:
            pass

        # Row 1: File input
        row_file = ttk.Frame(frm)
        row_file.pack(fill='x', pady=4)
        self.entry_input = ttk.Entry(row_file)
        self.entry_input.pack(side='left', fill='x', expand=True)
        ttk.Button(row_file, text='Abrir arquivo', command=self.open_file).pack(side='left', padx=4)
        ttk.Button(row_file, text='Exportar p/ JSON', command=self.export_rpg).pack(side='left')
        ttk.Button(row_file, text='Importar p/ Save', command=self.import_json_action).pack(side='left')

        # Row 2: Filename label
        self.lbl_filename = ttk.Label(frm, text='Nenhum arquivo carregado', anchor='w')
        self.lbl_filename.pack(fill='x', pady=(2,6))

        # Row 3: Options
        row3 = ttk.Frame(frm)
        row3.pack(fill='x', pady=6)
        ttk.Label(row3, text='Compressão:').pack(side='left')
        self.comb_comp = ttk.Combobox(row3, values=['gzip','zlib','none'], width=8)
        self.comb_comp.set('gzip')
        self.comb_comp.pack(side='left', padx=6)
        ttk.Label(row3, text='Encoding:').pack(side='left')
        self.comb_enc = ttk.Combobox(row3, values=['lzstring','none'], width=10)
        self.comb_enc.set('lzstring')
        self.comb_enc.pack(side='left', padx=6)

        # Row 4: Log controls
        row4 = ttk.Frame(frm)
        row4.pack(fill='x', pady=4)
        ttk.Button(row4, text='Preview JSON (tree)', command=self.preview_json).pack(side='left')
        ttk.Button(row4, text='Limpar log', command=self.clear_log).pack(side='left', padx=8)
        self.btn_show_log = ttk.Button(row4, text='Mostrar Log', command=self.toggle_log_window)
        self.btn_show_log.pack(side='left', padx=6)

        # Split Pane
        split = ttk.Panedwindow(frm, orient='horizontal')
        split.pack(fill='both', expand=True)

        left = ttk.LabelFrame(split, text='Preview')
        right = ttk.LabelFrame(split, text='Editor')
        split.add(left, weight=3)
        split.add(right, weight=2)

        # Treeview
        self.tree = ttk.Treeview(left, columns=('value',), show='tree headings')
        self.tree.heading('#0', text='Key')
        self.tree.heading('value', text='Value')
        try:
            self.tree.column('#0', width=420, stretch=True)
            self.tree.column('value', width=240, stretch=True)
        except Exception:
            pass
        ysb = ttk.Scrollbar(left, orient='vertical', command=self.tree.yview)
        xsb = ttk.Scrollbar(left, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscroll=ysb.set, xscroll=xsb.set)
        self.tree.pack(fill='both', expand=True, side='left')
        ysb.pack(fill='y', side='right')
        xsb.pack(fill='x', side='bottom')
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        try:
            self.tree.tag_configure('pulse', background='#fff3a6')
        except Exception:
            pass

        # Editor Pane
        edframe = ttk.Frame(right)
        edframe.pack(fill='both', expand=True)
        ttk.Label(edframe, text='Editor de campo', style='Header.TLabel').pack(anchor='w')
        self.entry_field = ttk.Entry(edframe)
        self.entry_field.pack(fill='x', padx=4, pady=4)
        btns = ttk.Frame(edframe)
        btns.pack(fill='x')
        ttk.Button(btns, text='Salvar campo', command=self.save_field).pack(side='left')
        ttk.Button(btns, text='Salvar JSON', command=self.save_json_file).pack(side='left', padx=4)
        ttk.Button(btns, text='Aplicar ao Save', command=self.apply_to_rpgsave).pack(side='left', padx=4)

        # Shortcuts
        ttk.Separator(edframe, orient='horizontal').pack(fill='x', pady=(8,6))
        shf = ttk.Frame(edframe)
        shf.pack(fill='x', pady=(0,6))
        ttk.Label(shf, text='Atalhos:', style='Header.TLabel').pack(anchor='w')
        sf_row = ttk.Frame(shf)
        sf_row.pack(fill='x')
        ttk.Button(sf_row, text='Itens', command=lambda: self.navigate_shortcut(['data','party','_items'])).pack(side='left', padx=4, pady=2)
        ttk.Button(sf_row, text='Gold', command=lambda: self.navigate_shortcut(['data','party','_gold'])).pack(side='left', padx=4, pady=2)
        ttk.Button(sf_row, text='Weapons', command=lambda: self.navigate_shortcut(['data','party','_weapons'])).pack(side='left', padx=4, pady=2)
        ttk.Button(sf_row, text='Vars', command=lambda: self.navigate_shortcut(['data','variables','_data'])).pack(side='left', padx=4, pady=2)
        ttk.Button(sf_row, text='Atores', command=self.ask_and_navigate_actor).pack(side='left', padx=4, pady=2)

        qa = ttk.Frame(shf)
        qa.pack(fill='x', pady=(6,0))
        ttk.Button(qa, text='Set Gold...', command=self.set_gold_custom).pack(side='left', padx=4)
        ttk.Button(qa, text='Max Gold', command=self.set_max_gold).pack(side='left', padx=4)
        ttk.Button(qa, text='Liberar All', command=self.ask_and_unlock_items).pack(side='left', padx=4)

        # Mappings
        ttk.Separator(edframe, orient='horizontal').pack(fill='x', pady=(8,6))
        mapf = ttk.Frame(edframe)
        mapf.pack(fill='x')
        ttk.Label(mapf, text='Mappings (Nomes):', style='Header.TLabel').pack(anchor='w')
        mf_row = ttk.Frame(mapf)
        mf_row.pack(fill='x', pady=(4,0))
        ttk.Button(mf_row, text='Items', command=lambda: self.load_mapping('items')).pack(side='left', padx=4)
        ttk.Button(mf_row, text='Weapons', command=lambda: self.load_mapping('weapons')).pack(side='left', padx=4)
        ttk.Button(mf_row, text='Armors', command=lambda: self.load_mapping('armors')).pack(side='left', padx=4)
        ttk.Button(mf_row, text='Actors', command=lambda: self.load_mapping('actors')).pack(side='left', padx=4)
        mf_row2 = ttk.Frame(mapf)
        mf_row2.pack(fill='x', pady=(4,0))
        ttk.Button(mf_row2, text='⚡ Auto Data/', command=self.auto_load_data_dir).pack(side='left', padx=4)
        ttk.Button(mf_row2, text='Limpar mappings', command=self.clear_mappings).pack(side='left', padx=4)

        # Filters
        filter_row = ttk.Frame(frm)
        filter_row.pack(fill='x', pady=(4,6))
        ttk.Label(filter_row, text='Filtro nome:').pack(side='left')
        self.filter_name_var = tk.StringVar()
        self.entry_filter_name = ttk.Entry(filter_row, textvariable=self.filter_name_var)
        self.entry_filter_name.pack(side='left', padx=4)
        ttk.Label(filter_row, text='Filtro valor:').pack(side='left', padx=(8,0))
        self.filter_value_var = tk.StringVar()
        self.entry_filter_value = ttk.Entry(filter_row, textvariable=self.filter_value_var)
        self.entry_filter_value.pack(side='left', padx=4)
        ttk.Button(filter_row, text='Filtrar', command=self.apply_filters).pack(side='left', padx=6)
        ttk.Button(filter_row, text='Limpar', command=self.clear_filters).pack(side='left')

        # Status
        self.status = ttk.Label(self, text='Arraste um .rpgsave/.rmmzsave ou .json aqui', relief='sunken', anchor='w')
        self.status.pack(side='bottom', fill='x')

        # State
        self.json_data = None
        self.json_path = None
        self._item_to_path = {}
        self._selected_item = None
        self.mappings = {'items': {}, 'weapons': {}, 'actors': {}, 'armors': {}}
        self._log_buffer = []
        self._log_win = None
        self._log_text = None
        self._anim_logging = False
        self._anim_tree_tasks = {}

    # --- Métodos de UI adaptados para Thread Safety ---

    def log(self, *parts):
        """Append log (Thread-Safe Wrapper)."""
        msg = ' '.join(str(p) for p in parts)
        # Se for chamado de uma thread secundária, não temos problema em acessar _log_buffer,
        # mas atualizar o widget de texto deve ser na main thread.
        # Simplificando: sempre joga para queue se houver janela aberta.
        self.queue_ui(self._log_internal, msg)

    def _log_internal(self, msg):
        self._log_buffer.append(msg)
        if getattr(self, '_log_text', None):
            try:
                self._log_text.insert('end', msg + '\n')
                self._log_text.see('end')
            except Exception:
                pass
        else:
            if getattr(self, 'btn_show_log', None) and not getattr(self, '_anim_logging', False):
                self.start_log_pulse()

    def update_filename_label(self, name: str | Path | None):
        self.queue_ui(self._update_filename_label_internal, name)

    def _update_filename_label_internal(self, name):
        if name is None:
            txt = 'Nenhum arquivo carregado'
        else:
            txt = f'Arquivo: {str(name)}'
        if hasattr(self, 'lbl_filename'):
            self.lbl_filename.config(text=txt)

    def animate_status_flash(self, msg: str):
        self.queue_ui(self._animate_status_flash_internal, msg)

    def _animate_status_flash_internal(self, msg):
        if not hasattr(self, 'status'): return
        prev = self.status.cget('text')
        self.status.configure(text=msg, style='Status.Highlight.TLabel')
        def _end():
            self.status.configure(text=prev, style='')
        self.after(1200, _end)

    # --- Animações (mantidas, mas chamadas via queue se necessário) ---

    def start_log_pulse(self):
        if getattr(self, '_anim_logging', False): return
        self._anim_logging = True
        try:
            self._orig_btn_style = self.btn_show_log.cget('style')
        except Exception:
            self._orig_btn_style = ''

        self._log_pulse_state = False

        def _step():
            if not getattr(self, '_anim_logging', False):
                self.btn_show_log.configure(style=self._orig_btn_style or '')
                return
            self._log_pulse_state = not self._log_pulse_state
            style = 'Alert.TButton' if self._log_pulse_state else (self._orig_btn_style or '')
            self.btn_show_log.configure(style=style)
            self.after(600, _step)

        self.after(0, _step)

    def stop_log_pulse(self):
        self._anim_logging = False

    def toggle_log_window(self):
        if getattr(self, '_log_win', None) and tk.Toplevel.winfo_exists(self._log_win):
            self._log_win.destroy()
            self._log_win = None
            self._log_text = None
            return

        win = tk.Toplevel(self)
        win.title('Log / Saída')
        txt = tk.Text(win, wrap='none')
        ysb = ttk.Scrollbar(win, orient='vertical', command=txt.yview)
        xsb = ttk.Scrollbar(win, orient='horizontal', command=txt.xview)
        txt.configure(yscroll=ysb.set, xscroll=xsb.set)
        txt.pack(fill='both', expand=True, side='left')
        ysb.pack(fill='y', side='right')
        xsb.pack(fill='x', side='bottom')

        for ln in getattr(self, '_log_buffer', []):
            txt.insert('end', ln + '\n')
        txt.see('end')

        self._log_win = win
        self._log_text = txt
        self.stop_log_pulse()

    # --- File Operations ---

    def open_file(self):
        p = filedialog.askopenfilename(
            title='Abrir arquivo',
            filetypes=[('Save Games', RPGSAVE_EXTS), ('JSON','*.json'), ('All','*.*')]
        )
        if not p: return
        self.entry_input.delete(0, 'end')
        self.entry_input.insert(0, p)
        self.preview_json()

    def export_rpg(self):
        src = self.entry_input.get().strip()
        if not src or not src.lower().endswith(RPGSAVE_TUPLE):
            p = filedialog.askopenfilename(title='Escolha save para exportar', filetypes=[('Save Games', RPGSAVE_EXTS)])
            if not p: return
            src = p

        dst = filedialog.asksaveasfilename(
            title='Salvar JSON como',
            defaultextension='.json',
            filetypes=[('JSON','*.json')],
            initialfile=Path(src).stem + '.json'
        )
        if not dst: return

        if export_rpgsave is None:
            messagebox.showerror('Erro', 'Script de exportação não encontrado')
            return

        def job():
            self.log(f'Exportando {src} -> {dst}')
            try:
                export_rpgsave(Path(src), Path(dst))
                self.log('Export concluído')
                self.animate_status_flash('Export concluído')
            except Exception as e:
                self.log('Erro export:', e)
                self.log(traceback.format_exc())

        self._run_in_thread(job)

    def import_json_action(self):
        src = self.entry_input.get().strip()
        if not src:
            p = filedialog.askopenfilename(title='Fonte', filetypes=[('JSON','*.json'),('Save Games', RPGSAVE_EXTS)])
            if not p: return
            src = p

        # Determina extensão padrão baseado no nome ou usa .rpgsave
        def_ext = '.rmmzsave' if '.rmmzsave' in src.lower() else '.rpgsave'

        dst = filedialog.asksaveasfilename(
            title='Salvar RPGSave como',
            defaultextension=def_ext,
            filetypes=[('RPGSave','*.rpgsave'), ('MZ Save', '*.rmmzsave')],
            initialfile=Path(src).stem + def_ext
        )
        if not dst: return

        compression = self.comb_comp.get()
        encoding = self.comb_enc.get()

        if import_json is None:
            messagebox.showerror('Erro', 'Script de importação não encontrado')
            return

        def job():
            try:
                if src.lower().endswith(RPGSAVE_TUPLE):
                    # Re-aplicar (Save -> Temp JSON -> Save)
                    import tempfile, os
                    tmp = Path(tempfile.mktemp(suffix='.json'))
                    try:
                        self.log('Convertendo fonte para JSON temporário...')
                        export_rpgsave(Path(src), tmp)
                        self.log(f'Importando para {dst}...')
                        import_json(tmp, Path(dst), forced_compression=(compression if compression!='none' else None), encoding=encoding)
                        self.log('Re-aplicação concluída')
                        self.animate_status_flash('Concluído')
                    finally:
                        if tmp.exists(): os.remove(tmp)
                else:
                    self.log(f'Importando {src} -> {dst}')
                    import_json(Path(src), Path(dst), forced_compression=(compression if compression!='none' else None), encoding=encoding)
                    self.log('Import concluído')
                    self.animate_status_flash('Concluído')
            except Exception as e:
                self.log('Erro import:', e)
                self.log(traceback.format_exc())

        self._run_in_thread(job)

    def preview_json(self):
        src = self.entry_input.get().strip()
        if not src:
            messagebox.showwarning('Aviso', 'Selecione um arquivo')
            return

        def job():
            self.queue_ui(self.clear_view)
            try:
                j_text = ""
                if src.lower().endswith(RPGSAVE_TUPLE):
                    import tempfile, os
                    tmp = Path(tempfile.mktemp(suffix='.json'))
                    try:
                        export_rpgsave(Path(src), tmp)
                        j_text = tmp.read_text(encoding='utf-8')
                    finally:
                        if tmp.exists(): os.remove(tmp)
                else:
                    j_text = Path(src).read_text(encoding='utf-8-sig')

                data = json.loads(j_text)

                # A atualização da Treeview deve ser na main thread
                self.queue_ui(self.finish_preview, data, src if not src.lower().endswith(RPGSAVE_TUPLE) else None, Path(src).name)

            except Exception as e:
                self.log('Erro preview:', e)
                self.log(traceback.format_exc())

        self._run_in_thread(job)

    def finish_preview(self, data, json_path, filename_lbl):
        self.json_data = data
        self.json_path = json_path
        self._update_filename_label_internal(filename_lbl)
        self.populate_tree()
        self.log('JSON carregado no preview')
        self._animate_status_flash_internal('Preview carregado')

    def apply_to_rpgsave(self):
        if self.json_data is None: return

        dst = filedialog.asksaveasfilename(
            title='Salvar RPGSave como',
            defaultextension='.rpgsave',
            filetypes=[('RPGSave','*.rpgsave'), ('MZ Save', '*.rmmzsave')]
        )
        if not dst: return

        compression = self.comb_comp.get()
        encoding = self.comb_enc.get()

        def job():
            import tempfile, os
            tmp = Path(tempfile.mktemp(suffix='.json'))
            try:
                tmp.write_text(json.dumps(self.json_data, ensure_ascii=False, indent=2), encoding='utf-8')
                import_json(tmp, Path(dst), forced_compression=(compression if compression!='none' else None), encoding=encoding)
                self.log('Salvo:', dst)
                self.animate_status_flash('Salvo com sucesso')
            except Exception as e:
                self.log('Erro:', e)
            finally:
                if tmp.exists(): os.remove(tmp)

        self._run_in_thread(job)

    # --- Helpers genéricos ---

    def _run_in_thread(self, fn, *a, **k):
        def job():
            try:
                fn(*a, **k)
            except Exception as e:
                self.log('Erro Thread:', e)
            finally:
                self.queue_ui(self.enable_buttons, True)

        self.enable_buttons(False)
        t = threading.Thread(target=job, daemon=True)
        t.start()

    def enable_buttons(self, enable: bool):
        # Desabilita/Habilita botões principais
        state = 'normal' if enable else 'disabled'
        for child in self.winfo_children():
            # Tenta desabilitar widgets filhos diretos se for frame
            for sub in child.winfo_children():
                try:
                    sub.configure(state=state)
                except Exception:
                    pass

    def clear_view(self):
        self.tree.delete(*self.tree.get_children())
        self.entry_field.delete(0, 'end')
        self._item_to_path = {}
        self._selected_item = None
        self._update_filename_label_internal(None)

    def save_field(self):
        if not self._selected_item: return
        txt = self.entry_field.get()
        path = self._item_to_path.get(self._selected_item)
        if not path: return
        try:
            newval = json.loads(txt)
        except Exception:
            newval = txt
        if self.set_by_path(path, newval):
            self.tree.set(self._selected_item, 'value', repr(newval))
            self.log('Campo salvo:', path)

    def save_json_file(self):
        if self.json_data is None: return
        pth = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON','*.json')])
        if not pth: return
        Path(pth).write_text(json.dumps(self.json_data, ensure_ascii=False, indent=2), encoding='utf-8')
        self.log('JSON salvo:', pth)
        self.animate_status_flash('JSON salvo')

    def on_drop(self, event):
        files = self.tk.splitlist(event.data)
        if not files: return
        f = files[0]
        self.entry_input.delete(0, 'end')
        self.entry_input.insert(0, f)
        self.preview_json()

    # --- Tree Logic (Mantida similar, apenas filtros e navegação) ---
    # Nota: O código da TreeView é extenso e não foi alterado significativamente
    # além das chamadas de thread.

    def populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        self._item_to_path = {}

        name_filter = self.filter_name_var.get().strip().lower()
        value_filter = self.filter_value_var.get().strip().lower()
        has_filter = bool(name_filter or value_filter)

        def make_display_key(key, path):
            try:
                parent_path = path[:-1]
                if parent_path == ['data', 'party', '_items']:
                    name = self.mappings['items'].get(str(key), '')
                    return f"{key}: {name}" if name else str(key)
                if parent_path == ['data', 'party', '_weapons']:
                    name = self.mappings['weapons'].get(str(key), '')
                    return f"{key}: {name}" if name else str(key)
                if parent_path == ['data', 'party', '_armors']:
                    name = self.mappings['armors'].get(str(key), '')
                    return f"{key}: {name}" if name else str(key)
                if len(path) == 5 and path[:4] == ['data', 'actors', '_data', '@a']:
                    actor_obj = self.get_by_path(path)
                    if isinstance(actor_obj, dict):
                        act_id = actor_obj.get('_actorId', key)
                        act_name = actor_obj.get('_name') or self.mappings['actors'].get(str(act_id), '')
                        act_lvl = actor_obj.get('_level', '')
                        extra = f": {act_name}" if act_name else ""
                        if act_lvl != '':
                            extra += f" (Lv {act_lvl})"
                        return f"Ator [{key}]{extra}"
                elif len(path) == 4 and path[:3] == ['data', 'actors', '_data'] and path[3] not in ('@c', '@'):
                    actor_obj = self.get_by_path(path)
                    if isinstance(actor_obj, dict):
                        act_id = actor_obj.get('_actorId', key)
                        act_name = actor_obj.get('_name') or self.mappings['actors'].get(str(act_id), '')
                        extra = f": {act_name}" if act_name else ""
                        return f"Ator [{key}]{extra}"
            except Exception:
                pass
            return str(key)

        def matches_filter(display, val_str):
            if name_filter and name_filter not in str(display).lower():
                return False
            if value_filter and value_filter not in str(val_str).lower():
                return False
            return True

        def insert_node(parent, key, value, path):
            display = make_display_key(key, path)
            is_container = isinstance(value, (dict, list))
            val_str = '{...}' if isinstance(value, dict) else ('[...]' if isinstance(value, list) else repr(value))

            self_match = matches_filter(display, "" if is_container else val_str)

            if is_container:
                node = self.tree.insert(parent or '', 'end', text=display, values=(val_str,))
                self._item_to_path[node] = list(path)

                child_matched = False
                if isinstance(value, dict):
                    for k, v in value.items():
                        if insert_node(node, k, v, path + [k]):
                            child_matched = True
                else:
                    for i, v in enumerate(value):
                        if insert_node(node, i, v, path + [i]):
                            child_matched = True

                if has_filter:
                    if self_match or child_matched:
                        self.tree.item(node, open=True)
                        return True
                    else:
                        self.tree.delete(node)
                        self._item_to_path.pop(node, None)
                        return False
                return True
            else:
                if has_filter and not self_match:
                    return False
                node = self.tree.insert(parent or '', 'end', text=display, values=(val_str,))
                self._item_to_path[node] = list(path)
                return True

        if self.json_data is None: return

        if isinstance(self.json_data, dict) and 'data' in self.json_data:
            insert_node('', 'data', self.json_data['data'], ['data'])
        else:
            insert_node('', 'root', self.json_data, [])

    # --- Navegação / Helpers ---

    def get_by_path(self, path):
        cur = self.json_data
        try:
            for p in path:
                if isinstance(cur, dict): cur = cur.get(p)
                elif isinstance(cur, list): cur = cur[int(p)]
                else: return None
            return cur
        except Exception:
            return None

    def set_by_path(self, path, value):
        if not path:
            self.json_data = value
            return True
        cur = self.json_data
        try:
            for i, p in enumerate(path):
                if i == len(path)-1:
                    if isinstance(cur, dict): cur[p] = value
                    elif isinstance(cur, list): cur[int(p)] = value
                    return True
                else:
                    if isinstance(cur, dict): cur = cur[p]
                    elif isinstance(cur, list): cur = cur[int(p)]
        except Exception:
            return False
        return False

    def on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        self._selected_item = sel[0]
        path = self._item_to_path.get(self._selected_item)
        if path:
            val = self.get_by_path(path)
            self.entry_field.delete(0, 'end')
            if isinstance(val, (dict, list)):
                self.entry_field.insert(0, f'<{type(val).__name__}>')
            else:
                self.entry_field.insert(0, str(val))

    def navigate_shortcut(self, target_path):
        if self.json_data is None:
            messagebox.showwarning('Aviso', 'Nenhum save carregado.')
            return

        target_list = [str(p) for p in target_path]
        target_node = None

        # 1. Procura exata
        for node, path in self._item_to_path.items():
            if [str(p) for p in path] == target_list:
                target_node = node
                break

        # 2. Procura por prefixo se não achou exato
        if not target_node:
            for node, path in self._item_to_path.items():
                str_path = [str(p) for p in path]
                if str_path[:len(target_list)] == target_list:
                    target_node = node
                    break

        if target_node:
            curr = self.tree.parent(target_node)
            while curr:
                self.tree.item(curr, open=True)
                curr = self.tree.parent(curr)

            if self.tree.get_children(target_node):
                self.tree.item(target_node, open=True)

            self.tree.selection_set(target_node)
            self.tree.focus(target_node)
            self.tree.see(target_node)
            self.on_tree_select(None)
            self.animate_status_flash(f'Navegado para: {" -> ".join(target_list)}')
            self.log(f'Navegado para: {" -> ".join(target_list)}')
        else:
            self.log(f'Caminho não encontrado na árvore: {" -> ".join(target_list)}')
            messagebox.showinfo('Aviso', f'Caminho não encontrado no save atual:\n{" -> ".join(target_list)}')

    def ask_and_navigate_actor(self):
        if self.json_data is None:
            messagebox.showwarning('Aviso', 'Nenhum save carregado.')
            return

        actors_container = self.get_by_path(['data', 'actors', '_data'])
        if not actors_container:
            messagebox.showinfo('Aviso', 'Dados de atores não encontrados no save.')
            return

        actor_list = []
        if isinstance(actors_container, dict) and '@a' in actors_container:
            raw_actors = actors_container['@a']
            base_path = ['data', 'actors', '_data', '@a']
        elif isinstance(actors_container, list):
            raw_actors = actors_container
            base_path = ['data', 'actors', '_data']
        elif isinstance(actors_container, dict):
            raw_actors = actors_container
            base_path = ['data', 'actors', '_data']
        else:
            raw_actors = []
            base_path = ['data', 'actors', '_data']

        if isinstance(raw_actors, (list, tuple)):
            for idx, a in enumerate(raw_actors):
                if isinstance(a, dict):
                    aid = a.get('_actorId', idx)
                    aname = a.get('_name') or self.mappings['actors'].get(str(aid), f"Ator {aid}")
                    alvl = a.get('_level', 1)
                    actor_list.append((idx, aid, aname, alvl, base_path + [idx]))
        elif isinstance(raw_actors, dict):
            for k, a in raw_actors.items():
                if k in ('@c', '@'): continue
                if isinstance(a, dict):
                    aid = a.get('_actorId', k)
                    aname = a.get('_name') or self.mappings['actors'].get(str(aid), f"Ator {aid}")
                    alvl = a.get('_level', 1)
                    actor_list.append((k, aid, aname, alvl, base_path + [k]))

        if not actor_list:
            messagebox.showinfo('Aviso', 'Nenhum ator ativo encontrado.')
            return

        dlg = tk.Toplevel(self)
        dlg.title("Selecionar Ator")
        dlg.geometry("400x340")
        dlg.transient(self)
        dlg.grab_set()

        ttk.Label(dlg, text="Selecione um ator para inspecionar:", style='Header.TLabel').pack(anchor='w', padx=10, pady=(10, 4))

        listbox_frm = ttk.Frame(dlg)
        listbox_frm.pack(fill='both', expand=True, padx=10, pady=4)
        sb = ttk.Scrollbar(listbox_frm, orient='vertical')
        lb = tk.Listbox(listbox_frm, yscrollcommand=sb.set, font=('TkDefaultFont', 9))
        sb.config(command=lb.yview)
        lb.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        for item in actor_list:
            idx, aid, aname, alvl, path = item
            lb.insert('end', f"ID {str(aid).rjust(3, '0')} | {aname} (Nível {alvl})")
        lb.selection_set(0)

        def on_select():
            sel = lb.curselection()
            if sel:
                chosen = actor_list[sel[0]]
                dlg.destroy()
                self.navigate_shortcut(chosen[4])

        btn_frm = ttk.Frame(dlg)
        btn_frm.pack(fill='x', padx=10, pady=10)
        ttk.Button(btn_frm, text="Ir para Ator", command=on_select).pack(side='right', padx=4)
        ttk.Button(btn_frm, text="Cancelar", command=dlg.destroy).pack(side='right')
        lb.bind('<Double-Button-1>', lambda e: on_select())

    def set_gold_custom(self):
        if self.json_data is None:
            messagebox.showwarning('Aviso', 'Nenhum save carregado.')
            return

        current_gold = self.get_by_path(['data', 'party', '_gold'])
        if current_gold is None:
            current_gold = 0

        val = simpledialog.askinteger(
            "Definir Gold",
            "Digite a quantidade de Gold:",
            initialvalue=current_gold,
            minvalue=0,
            maxvalue=999999999,
            parent=self
        )
        if val is not None:
            self.set_by_path(['data', 'party', '_gold'], val)
            self.populate_tree()
            self.navigate_shortcut(['data', 'party', '_gold'])
            self.log(f"Gold definido para: {val:,}")
            self.animate_status_flash(f"Gold alterado para {val:,}")

    def set_max_gold(self):
        if self.json_data is None:
            messagebox.showwarning('Aviso', 'Nenhum save carregado.')
            return
        self.set_by_path(['data', 'party', '_gold'], 99999999)
        self.populate_tree()
        self.navigate_shortcut(['data', 'party', '_gold'])
        self.log('Gold maxed: 99.999.999')
        self.animate_status_flash('Gold maximizado para 99.999.999!')

    def ask_and_unlock_items(self):
        if self.json_data is None:
            messagebox.showwarning('Aviso', 'Nenhum save carregado.')
            return

        party_items = self.get_by_path(['data', 'party', '_items'])
        if party_items is None:
            messagebox.showinfo('Aviso', 'Seção party._items não encontrada no save.')
            return

        qty = simpledialog.askinteger(
            "Liberar Itens",
            "Defina a quantidade para cada item:",
            initialvalue=99,
            minvalue=1,
            maxvalue=999,
            parent=self
        )
        if qty is None: return

        if not self.mappings.get('items'):
            if messagebox.askyesno("Carregar Itens?", "Nenhum banco de dados de itens está carregado.\nDeseja tentar carregar a pasta 'data' agora para desbloquear todos os itens do jogo?"):
                self.auto_load_data_dir()

        added_count = 0
        if self.mappings.get('items'):
            for item_id in self.mappings['items']:
                party_items[str(item_id)] = qty
                added_count += 1
        else:
            for k in list(party_items.keys()):
                if not str(k).startswith('@'):
                    party_items[k] = qty
                    added_count += 1

        self.populate_tree()
        self.navigate_shortcut(['data', 'party', '_items'])
        self.log(f"{added_count} itens atualizados com quantidade {qty}.")
        self.animate_status_flash(f"{added_count} itens atualizados (x{qty})!")

    def auto_load_data_dir(self, directory=None):
        if not directory:
            candidates = []
            if self.entry_input.get().strip():
                src_p = Path(self.entry_input.get().strip())
                candidates.append(src_p.parent / 'data')
                candidates.append(src_p.parent.parent / 'data')
                candidates.append(src_p.parent.parent / 'save' / 'data')
            candidates.append(ROOT_DIR / 'save' / 'data')
            candidates.append(ROOT_DIR / 'data')

            for c in candidates:
                if c.is_dir() and (c / 'Items.json').exists():
                    directory = c
                    break

        if not directory:
            d = filedialog.askdirectory(title='Selecione a pasta data do jogo (com Items.json, etc.)')
            if not d: return
            directory = Path(d)

        loaded = []
        mapping_files = {
            'items': 'Items.json',
            'weapons': 'Weapons.json',
            'armors': 'Armors.json',
            'actors': 'Actors.json'
        }
        for kind, filename in mapping_files.items():
            fpath = Path(directory) / filename
            if fpath.exists():
                try:
                    data = json.loads(fpath.read_text(encoding='utf-8-sig'))
                    mp = {}
                    lst = data if isinstance(data, list) else data.get('data', [])
                    for item in lst:
                        if item and 'id' in item and 'name' in item:
                            mp[str(item['id'])] = item['name']
                    self.mappings[kind] = mp
                    loaded.append(f"{kind} ({len(mp)})")
                except Exception as e:
                    self.log(f"Erro ao carregar {filename}: {e}")

        if loaded:
            self.populate_tree()
            msg = f"Mappings carregados de {Path(directory).name}: {', '.join(loaded)}"
            self.log(msg)
            self.animate_status_flash("Mappings carregados com sucesso!")
        else:
            messagebox.showwarning("Aviso", "Nenhum arquivo de banco de dados (Items.json, etc.) encontrado na pasta.")

    def load_mapping(self, kind):
        p = filedialog.askopenfilename(filetypes=[('JSON','*.json')])
        if not p: return
        try:
            data = json.loads(Path(p).read_text(encoding='utf-8-sig'))
            mp = {}
            lst = data if isinstance(data, list) else data.get('data', [])
            for item in lst:
                if item and 'id' in item and 'name' in item:
                    mp[str(item['id'])] = item['name']
            self.mappings[kind] = mp
            self.populate_tree()
            self.log(f'Mapping {kind} carregado ({len(mp)} entradas)')
            self.animate_status_flash(f'Mapping {kind} carregado!')
        except Exception as e:
            self.log('Erro mapping:', e)

    def clear_mappings(self):
        self.mappings = {k: {} for k in self.mappings}
        self.populate_tree()
        self.log('Mappings limpos')
        self.animate_status_flash('Mappings limpos')

    def apply_filters(self):
        self.populate_tree()

    def clear_filters(self):
        self.filter_name_var.set('')
        self.filter_value_var.set('')
        self.populate_tree()

    def clear_log(self):
        self._log_buffer = []
        if self._log_text: self._log_text.delete('1.0', 'end')


def main():
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()
