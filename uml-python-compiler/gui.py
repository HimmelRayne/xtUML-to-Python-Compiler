"""Tkinter interface for the UML Class Diagram Compiler.

Run with ``python gui.py`` from the project directory.
"""

import os
import pprint
import tkinter as tk
from dataclasses import asdict
from tkinter import filedialog, messagebox, ttk

from errors.errors import CompilerError
from generator import PythonGenerator
from lexer import Lexer
from semantic import SemanticAnalyzer
from uml_parser import Parser


ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SOURCE = os.path.join("examples", "basic.uml")
DEFAULT_OUTPUT = os.path.join("output", "output.py")

COLORS = {
    "background": "#f3f6fb",
    "surface": "#ffffff",
    "surface_alt": "#f8fafc",
    "ink": "#17243a",
    "muted": "#63728a",
    "border": "#dce4ef",
    "accent": "#3659d9",
    "accent_hover": "#2948bd",
    "success": "#16845b",
    "error": "#c43d4d",
    "editor": "#101a2b",
    "editor_ink": "#e2eaf6",
    "editor_gutter": "#8190a8",
}


def clean_ast(value):
    """Remove source positions so the AST view stays readable."""
    if isinstance(value, dict):
        return {
            key: clean_ast(item)
            for key, item in value.items()
            if key not in ("line", "column") and not key.endswith("_pos")
        }
    if isinstance(value, list):
        return [clean_ast(item) for item in value]
    return value


def format_diagnostic(error, source):
    lines = source.splitlines()
    result = [str(error)]
    if 1 <= error.line <= len(lines):
        text = lines[error.line - 1].replace("\t", "    ")
        result.extend((f"  {text}", f"  {' ' * max(0, error.column - 1)}^"))
    return "\n".join(result)


class UMLCompilerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("UML Class Diagram Compiler")
        self.geometry("1280x820")
        self.minsize(960, 640)
        self.configure(bg=COLORS["background"])

        self.source_path = None
        self.output_path = tk.StringVar(value=DEFAULT_OUTPUT)
        self.status_text = tk.StringVar(value="Siap. Buka atau tulis diagram UML untuk mulai.")
        self.source_text = None
        self.line_numbers = None
        self.result_tabs = None
        self.python_text = None
        self.diagnostics_text = None
        self.tokens_text = None
        self.ast_text = None
        self._configure_style()
        self._build_ui()
        self._load_initial_example()

    def _configure_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=COLORS["background"])
        style.configure("Panel.TFrame", background=COLORS["surface"])
        style.configure("TLabel", background=COLORS["background"], foreground=COLORS["ink"],
                        font=("Segoe UI", 10))
        style.configure("Muted.TLabel", foreground=COLORS["muted"])
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"), foreground=COLORS["ink"])
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground=COLORS["muted"])
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"), foreground=COLORS["ink"])
        style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=(12, 8),
                        background=COLORS["surface"], foreground=COLORS["ink"], bordercolor=COLORS["border"])
        style.map("TButton", background=[("active", "#edf2fa")])
        style.configure("Accent.TButton", background=COLORS["accent"], foreground="#ffffff",
                        bordercolor=COLORS["accent"])
        style.map("Accent.TButton", background=[("active", COLORS["accent_hover"])],
                  foreground=[("active", "#ffffff")])
        style.configure("TNotebook", background=COLORS["surface"], borderwidth=0)
        style.configure("TNotebook.Tab", background=COLORS["surface_alt"], foreground=COLORS["muted"],
                        padding=(14, 9), font=("Segoe UI", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", COLORS["surface"])],
                  foreground=[("selected", COLORS["accent"])])
        style.configure("TEntry", padding=(8, 7), fieldbackground=COLORS["surface"],
                        foreground=COLORS["ink"], bordercolor=COLORS["border"])
        style.configure("Status.TLabel", background=COLORS["surface"], foreground=COLORS["muted"],
                        padding=(14, 9), font=("Segoe UI", 9))

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(22, 18, 22, 14))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        title_block = ttk.Frame(header)
        title_block.grid(row=0, column=0, sticky="w")
        ttk.Label(title_block, text="xtUML Compiler", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_block, text="Terjemahkan diagram kelas xtUML menjadi kode Python",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(2, 0))

        actions = ttk.Frame(header)
        actions.grid(row=0, column=1, sticky="e", padx=(12, 0))
        ttk.Button(actions, text="Buka xtUML", command=self.open_source).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Simpan xtUML", command=self.save_source).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Compile", style="Accent.TButton",
                   command=self.compile_source).pack(side="left")

        main = ttk.Frame(self, padding=(18, 0, 18, 12))
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1, uniform="panels")
        main.columnconfigure(1, weight=1, uniform="panels")
        main.rowconfigure(0, weight=1)

        self._build_editor_panel(main)
        self._build_results_panel(main)

        status = ttk.Label(self, textvariable=self.status_text, style="Status.TLabel", anchor="w")
        status.grid(row=2, column=0, sticky="ew")

    def _build_editor_panel(self, parent):
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=16)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(2, weight=1)

        top = ttk.Frame(panel, style="Panel.TFrame")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 11))
        top.columnconfigure(0, weight=1)
        self.file_label = ttk.Label(top, text="Diagram xtUML", style="Section.TLabel")
        self.file_label.grid(row=0, column=0, sticky="w")
        self.sample_choice = tk.StringVar(value="Contoh: basic")
        samples = ["Contoh: basic", "Contoh: inheritance", "Contoh: relationship"]
        picker = ttk.Combobox(top, values=samples, textvariable=self.sample_choice,
                              state="readonly", width=23)
        picker.grid(row=0, column=1, sticky="e")
        picker.bind("<<ComboboxSelected>>", self.load_sample)

        editor_frame = tk.Frame(panel, bg=COLORS["editor"], highlightthickness=1,
                                highlightbackground=COLORS["border"])
        editor_frame.grid(row=2, column=0, sticky="nsew")
        editor_frame.rowconfigure(0, weight=1)
        editor_frame.columnconfigure(1, weight=1)
        self.line_numbers = tk.Text(editor_frame, width=4, padx=10, pady=13, takefocus=0,
                                    borderwidth=0, background="#17243a", foreground=COLORS["editor_gutter"],
                                    font=("Cascadia Code", 10), state="disabled", wrap="none")
        self.line_numbers.grid(row=0, column=0, sticky="ns")
        self.source_text = tk.Text(editor_frame, undo=True, padx=13, pady=13, borderwidth=0,
                                   background=COLORS["editor"], foreground=COLORS["editor_ink"],
                                   insertbackground="#ffffff", selectbackground="#334d76",
                                   font=("Cascadia Code", 10), wrap="none", tabs=(32,))
        self.source_text.grid(row=0, column=1, sticky="nsew")
        scroll_y = ttk.Scrollbar(editor_frame, orient="vertical", command=self._scroll_source)
        scroll_y.grid(row=0, column=2, sticky="ns")
        scroll_x = ttk.Scrollbar(panel, orient="horizontal", command=self.source_text.xview)
        scroll_x.grid(row=3, column=0, sticky="ew")
        self.source_text.configure(yscrollcommand=self._source_scrolled, xscrollcommand=scroll_x.set)
        self.source_text.bind("<<Modified>>", self._source_modified)
        self.source_text.bind("<KeyRelease>", self._refresh_line_numbers)
        self.source_text.bind("<MouseWheel>", self._refresh_line_numbers)
        self.source_text.bind("<Button-4>", self._refresh_line_numbers)
        self.source_text.bind("<Button-5>", self._refresh_line_numbers)

        output_row = ttk.Frame(panel, style="Panel.TFrame")
        output_row.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        output_row.columnconfigure(1, weight=1)
        ttk.Label(output_row, text="Simpan hasil ke", style="Muted.TLabel").grid(row=0, column=0,
                                                                                 sticky="w", padx=(0, 9))
        ttk.Entry(output_row, textvariable=self.output_path).grid(row=0, column=1, sticky="ew")
        ttk.Button(output_row, text="Pilih", command=self.choose_output).grid(row=0, column=2,
                                                                              padx=(7, 0))

    def _build_results_panel(self, parent):
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=16)
        panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        ttk.Label(panel, text="Hasil kompilasi", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 11))
        self.result_tabs = ttk.Notebook(panel)
        self.result_tabs.grid(row=1, column=0, sticky="nsew")
        self.python_text = self._add_output_tab("Python")
        self.diagnostics_text = self._add_output_tab("Diagnostik")
        self.tokens_text = self._add_output_tab("Token")
        self.ast_text = self._add_output_tab("AST")

    def _add_output_tab(self, label):
        frame = ttk.Frame(self.result_tabs, style="Panel.TFrame")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text = tk.Text(frame, padx=14, pady=14, borderwidth=0, wrap="none",
                       background=COLORS["surface_alt"], foreground=COLORS["ink"],
                       font=("Cascadia Code", 9), state="disabled")
        text.grid(row=0, column=0, sticky="nsew")
        ybar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        ybar.grid(row=0, column=1, sticky="ns")
        xbar = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
        xbar.grid(row=1, column=0, sticky="ew")
        text.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.result_tabs.add(frame, text=label)
        return text

    def _load_initial_example(self):
        path = os.path.join(ROOT, DEFAULT_SOURCE)
        if os.path.isfile(path):
            with open(path, encoding="utf-8-sig") as source_file:
                self._set_source(source_file.read(), path)
            self._replace_text(self.diagnostics_text, "Pilih Compile untuk menjalankan pipeline compiler.")
        self._refresh_line_numbers()

    def _source_modified(self, _event=None):
        if self.source_text.edit_modified():
            self.source_text.edit_modified(False)
            self._refresh_line_numbers()

    def _refresh_line_numbers(self, _event=None):
        if not self.source_text:
            return
        last_line = int(self.source_text.index("end-1c").split(".")[0])
        content = "\n".join(str(number) for number in range(1, last_line + 1))
        self.line_numbers.configure(state="normal")
        self.line_numbers.delete("1.0", "end")
        self.line_numbers.insert("1.0", content)
        self.line_numbers.configure(state="disabled")
        self.line_numbers.yview_moveto(self.source_text.yview()[0])

    def _source_scrolled(self, first, last):
        self.line_numbers.yview_moveto(first)
        self._refresh_line_numbers()

    def _scroll_source(self, *args):
        self.source_text.yview(*args)
        self._refresh_line_numbers()

    def _set_source(self, source, path=None):
        self.source_text.delete("1.0", "end")
        self.source_text.insert("1.0", source)
        self.source_text.edit_modified(False)
        self.source_path = path
        self.file_label.configure(text=os.path.basename(path) if path else "Diagram UML baru")
        self._refresh_line_numbers()

    def _get_source(self):
        return self.source_text.get("1.0", "end-1c")

    def _replace_text(self, widget, content):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def open_source(self):
        path = filedialog.askopenfilename(
            title="Buka diagram UML", initialdir=ROOT,
            filetypes=(("UML source", "*.uml"), ("Semua file", "*.*")))
        if not path:
            return
        try:
            with open(path, encoding="utf-8-sig") as source_file:
                source = source_file.read()
        except OSError as error:
            messagebox.showerror("Gagal membuka file", str(error), parent=self)
            return
        self._set_source(source, path)
        self.status_text.set(f"File dibuka: {path}")

    def save_source(self):
        path = self.source_path or filedialog.asksaveasfilename(
            title="Simpan diagram UML", initialdir=ROOT,
            defaultextension=".uml", filetypes=(("UML source", "*.uml"), ("Semua file", "*.*")))
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as source_file:
                source_file.write(self._get_source())
        except OSError as error:
            messagebox.showerror("Gagal menyimpan file", str(error), parent=self)
            return
        self.source_path = path
        self.file_label.configure(text=os.path.basename(path))
        self.status_text.set(f"Diagram disimpan: {path}")

    def load_sample(self, _event=None):
        name = self.sample_choice.get().replace("Contoh: ", "")
        path = os.path.join(ROOT, "examples", name + ".uml")
        try:
            with open(path, encoding="utf-8-sig") as sample_file:
                source = sample_file.read()
        except OSError as error:
            messagebox.showerror("Contoh tidak tersedia", str(error), parent=self)
            return
        self._set_source(source, path)
        self.status_text.set(f"Contoh dimuat: {name}.uml")

    def choose_output(self):
        current = self.output_path.get() or DEFAULT_OUTPUT
        path = filedialog.asksaveasfilename(
            title="Pilih file Python hasil", initialdir=os.path.dirname(os.path.join(ROOT, current)),
            initialfile=os.path.basename(current), defaultextension=".py",
            filetypes=(("Python", "*.py"), ("Semua file", "*.*")))
        if path:
            self.output_path.set(os.path.relpath(path, ROOT) if path.startswith(ROOT) else path)

    def compile_source(self):
        source = self._get_source()
        self.source_text.tag_remove("error_line", "1.0", "end")
        self._replace_text(self.diagnostics_text, "Menjalankan lexer dan parser...")
        self._replace_text(self.tokens_text, "")
        self._replace_text(self.ast_text, "")
        self._replace_text(self.python_text, "")
        self.update_idletasks()

        try:
            tokens = Lexer(source).tokenize()
            program = Parser(tokens).parse()
        except CompilerError as error:
            self._show_errors([error], source, "Parsing gagal")
            self._replace_text(self.tokens_text, "Token tidak tersedia karena parsing gagal.")
            self._replace_text(self.ast_text, "AST tidak tersedia karena parsing gagal.")
            return

        token_lines = [f"{'LOKASI':<10} {'TIPE':<14} NILAI"]
        token_lines.append("-" * 62)
        for token in tokens:
            value = repr(token.value) if token.value else "-"
            token_lines.append(f"{token.line}:{token.column:<7} {token.type.name:<14} {value}")
        self._replace_text(self.tokens_text, "\n".join(token_lines))
        self._replace_text(self.ast_text, pprint.pformat(clean_ast(asdict(program)),
                                                         sort_dicts=False, width=90))

        errors = SemanticAnalyzer().analyze(program)
        if errors:
            self._show_errors(errors, source, "Semantic analysis gagal")
            return

        code = PythonGenerator().generate(program)
        output = self.output_path.get().strip() or DEFAULT_OUTPUT
        if not os.path.isabs(output):
            output = os.path.join(ROOT, output)
        try:
            output = os.path.abspath(output)
            directory = os.path.dirname(output)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(output, "w", encoding="utf-8") as output_file:
                output_file.write(code)
        except OSError as error:
            self._replace_text(self.python_text, code)
            self._replace_text(self.diagnostics_text, f"Kode berhasil dibuat, tetapi file gagal disimpan.\n\n{error}")
            self.result_tabs.select(1)
            self.status_text.set("Kompilasi selesai dengan kendala penyimpanan.")
            return

        self.output_path.set(os.path.relpath(output, ROOT) if output.startswith(ROOT) else output)
        self._replace_text(self.python_text, code)
        self._replace_text(self.diagnostics_text,
                           "[OK] Parsing berhasil\n[OK] Tidak ada error semantic\n"
                           "[OK] Kode Python berhasil dibuat\n\n"
                           f"File output:\n{output}")
        self.result_tabs.select(0)
        self.status_text.set(f"Berhasil dikompilasi | {len(program.classes)} class | {output}")

    def _show_errors(self, errors, source, stage):
        details = [f"{stage} | {len(errors)} error" if len(errors) != 1 else stage, ""]
        details.extend(format_diagnostic(error, source) for error in errors)
        self._replace_text(self.diagnostics_text, "\n\n".join(details))
        self.result_tabs.select(1)
        first = errors[0]
        if first.line > 0:
            self.source_text.tag_remove("error_line", "1.0", "end")
            start = f"{first.line}.0"
            end = f"{first.line}.end"
            self.source_text.tag_add("error_line", start, end)
            self.source_text.tag_config("error_line", background="#3a2636")
            self.source_text.see(start)
        self.status_text.set(f"{stage}: {len(errors)} error ditemukan")


if __name__ == "__main__":
    UMLCompilerApp().mainloop()
