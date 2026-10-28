Syaiful Amri - 24106050040
Muhammad Ridwan Kurniawan - 24106050043
# xtUML Class Diagram Compiler

Compiler sederhana yang menerjemahkan **xtUML Class Diagram dalam bentuk teks** (`.uml`) menjadi **kode Python** (`.py`).
Project kuliah untuk mempraktikkan tahapan compiler: Lexer → Parser → AST → Semantic Analyzer → Code Generator.

## Tujuan

- Mempraktikkan pipeline compiler secara lengkap pada bahasa kecil (DSL).
- Menunjukkan bahwa tiap tahap punya tanggung jawab sendiri dan bisa diuji sendiri.
- Menghasilkan kerangka kode Python yang valid dari model UML (tanpa business logic).

Hanya memakai pustaka standar Python (3.8+), tanpa dependency tambahan.

## Fitur

- `class`, `abstract class`, `interface`
- Atribut dan method dengan visibility `+` (public), `-` (private), `#` (protected)
- Parameter method dan return type
- Inheritance (`extends`) dan implementasi interface (`implements`)
- Association `-->` dengan multiplicity dan nama relasi
- Komentar `// ...`
- Error syntax dan semantic dengan nomor baris/kolom dan kutipan baris sumber
- Semua error semantic dilaporkan sekaligus (tidak berhenti di error pertama)

## Grammar DSL

```
program        := (class_decl | rel_decl)* EOF
class_decl     := [ "abstract" ] ( "class" | "interface" ) IDENT
                  [ "extends" IDENT ] [ "implements" IDENT { "," IDENT } ]
                  "{" { member } "}"
member         := [ visibility ] IDENT ( attribute_rest | method_rest )
visibility     := "+" | "-" | "#"                 (default: +)
attribute_rest := ":" IDENT
method_rest    := "(" [ param { "," param } ] ")" [ ":" IDENT ]   (default return: void)
param          := IDENT ":" IDENT
rel_decl       := IDENT [ STRING ] "-->" [ STRING ] IDENT [ ":" IDENT ]
```

Aturan leksikal:

| Token | Keterangan |
|---|---|
| Keyword | `class abstract interface extends implements` |
| `IDENTIFIER` | `[A-Za-z_][A-Za-z0-9_]*` (hanya ASCII) |
| `STRING` | teks dalam tanda kutip ganda, dipakai untuk multiplicity |
| Simbol | `+ - # : { } ( ) , -->` |
| Komentar | `//` sampai akhir baris (`#` tidak dipakai karena sudah menjadi visibility protected) |

Multiplicity yang valid: `"1"`, `"*"`, `"0..1"`, `"1..*"`, `"2..5"` (batas bawah rentang harus angka dan tidak boleh lebih besar dari batas atas).

Tipe data: `int`, `float`, `str`, `string`, `bool`, `void` (hanya untuk return type), atau nama class/interface yang dideklarasikan.

## Arsitektur

```
Source .uml
   │
   ▼
Lexer              lexer/lexer.py              teks   → token (type, value, line, column)
   │
   ▼
Parser             uml_parser/parser.py        token  → AST  (recursive descent)
   │
   ▼
Semantic Analyzer  semantic/analyzer.py        AST    → daftar error + symbol table
   │
   ▼
Code Generator     generator/python_generator.py   AST (valid) → teks Python
   │
   ▼
output.py
```

| Folder / file | Tanggung jawab |
|---|---|
| `main.py` | CLI, menjalankan tahap secara berurutan dan melaporkan error |
| `lexer/` | Memecah teks menjadi token; error karakter tidak dikenal dan string tidak ditutup |
| `uml_parser/` | Memeriksa struktur sesuai grammar; membangun AST; validasi format multiplicity |
| `uml_ast/nodes.py` | Dataclass node AST: `Program`, `ClassNode`, `AttributeNode`, `MethodNode`, `ParameterNode`, `RelationshipNode` |
| `semantic/` | `symbol_table.py` (class dan anggotanya) dan `analyzer.py` (aturan validasi) |
| `generator/` | Mengubah AST yang sudah valid menjadi kode Python |
| `errors/errors.py` | `LexerError`, `ParserError` (label *Syntax Error*) dan `SemanticError` |

Catatan: folder `uml_ast/` dan `uml_parser/` sengaja tidak bernama `ast/` dan `parser/` karena bentrok dengan modul standar Python.

### Aturan semantic

| Aturan | Contoh pesan |
|---|---|
| Class duplikat | `Class 'A' is already defined (first defined at line 1)` |
| Parent / interface / ujung relasi tidak ada | `Class 'User' is not defined.` |
| Inheritance tidak valid | class `extends` interface, interface `extends` class, `implements` ke non-interface |
| Circular inheritance | `Circular inheritance detected: A -> B -> A` |
| Atribut / method / parameter duplikat | `Duplicate attribute 'x' in class 'A'.` |
| Tipe tidak dikenal | `Unknown type 'Foo'. Use a built-in type (...) or a declared class.` |
| `void` sebagai tipe atribut/parameter | `'void' cannot be used as the type of attribute 'x'.` |
| Interface punya atribut, atau menjadi sumber association | `Interface 'I' cannot declare attributes ('x').` |
| Atribut dan method bernama sama | `'x' is declared as both an attribute and a method in class 'A'.` |
| Nama berupa keyword Python atau `self` | `Attribute name 'pass' is a reserved Python word.` |
| Nama class bentrok dengan tipe bawaan / `ABC` | `Class name 'int' is reserved (...)` |

### Aturan generator

| xtUML | Python |
|---|---|
| `int`, `float`, `bool`, `str`, `string` | `int`, `float`, `bool`, `str`, `str` |
| `void` | `None` |
| `+ name` | `name` |
| `- name` dan `# name` | `_name` |
| `extends` | `class Admin(User):` dan `super().__init__(...)` |
| `abstract class`, `interface` | turunan `ABC`; semua method diberi `@abstractmethod` |
| Association, multiplicity target `*` atau batas atas > 1 | `self.nama: list[T] = []` |
| Association, selain itu | `self.nama: T \| None = None` |
| Method | body `pass` |

Konstruktor menerima semua atribut (milik parent dulu, lalu milik sendiri). Class diurutkan agar parent selalu terdefinisi lebih dulu. Nama field asosiasi diambil dari nama relasi, atau nama target dalam huruf kecil (ditambah `s` untuk koleksi).

## Cara menjalankan

Butuh Python 3.8+.

### Antarmuka Tkinter

Jalankan aplikasi desktop dari folder project:

```
python gui.py
```

Antarmuka menyediakan editor xtUML, contoh diagram, buka/simpan file, serta tab hasil
untuk kode Python, diagnostik, token, dan AST. Tombol **Compile** menjalankan pipeline
compiler dan menyimpan kode ke lokasi pada kolom output (default `output/output.py`).

```
python main.py examples/basic.uml
python main.py examples/inheritance.uml -o output/inheritance.py
python main.py examples/basic.uml --tokens --ast
```

| Opsi | Fungsi |
|---|---|
| `-o`, `--output` | Lokasi file keluaran (default `output/output.py`) |
| `--tokens` | Menampilkan daftar token |
| `--ast` | Menampilkan AST |

Exit code: `0` berhasil, `1` error syntax/semantic, `2` file tidak bisa dibaca/ditulis.

## Contoh

Input (potongan dari `examples/basic.uml`, class `Product` tidak ditampilkan):

```
class User {
    - id: int
    + name: str
    # email: str

    + login(): bool
    + changePassword(password: str): void
}
```

Perintah dan hasilnya:

```
$ python main.py examples/basic.uml
Parsing...
✓ Syntax valid

Semantic analysis...
✓ No semantic errors

Generating Python...
✓ Generated: output/output.py
```

Isi `output/output.py` (bagian `User`; `Product` ikut dihasilkan di bawahnya):

```python
# Generated by xtUML Class Diagram Compiler
from __future__ import annotations


class User:
    def __init__(self, id: int, name: str, email: str):
        self._id = id
        self.name = name
        self._email = email

    def login(self) -> bool:
        pass

    def changePassword(self, password: str) -> None:
        pass
```

Contoh lain: `examples/inheritance.uml` (extends, abstract class, interface) dan `examples/relationship.uml` (association, multiplicity, nama relasi). Contoh association:

```
User "1" --> "*" Product : owns
```

menghasilkan di dalam `User.__init__`:

```python
self.owns: list[Product] = []  # association: User "1" --> "*" Product
```

## Error handling

Setiap error menyebutkan jenis, pesan, baris, kolom, dan baris sumber. Pipeline berhenti pada tahap yang gagal: error lexer/parser menghentikan sebelum semantic analysis, dan error semantic menghentikan sebelum generasi kode (tidak ada file keluaran yang dibuat).

Syntax error (`examples/invalid/syntax_error.uml`):

```
Parsing...
Syntax Error: Expected ':' (attribute) or '(' (method), found 'str'
Line 3, Column 12
      + name str
             ^
```

Semantic error (`examples/invalid/semantic_error.uml`, 4 error dilaporkan sekaligus):

```
Semantic Error: Class 'User' is not defined.
Line 1, Column 21
  class Admin extends User {
                      ^
...
4 errors found.
```

Error ditulis ke stderr, status tahap ke stdout.

## Testing

```
python -m unittest discover -s tests -t .
```

| File | Isi |
|---|---|
| `tests/test_lexer.py` | token, posisi baris/kolom, error lexer |
| `tests/test_parser.py` | class kosong, atribut, method, parameter, inheritance, relasi, multiplicity, syntax error |
| `tests/test_semantic.py` | semua aturan semantic dan posisi error |
| `tests/test_generator.py` | kode hasil di-`compile()` dan sebagian di-`exec()` lalu diinstansiasi |
| `tests/test_cli.py` | end-to-end: semua contoh valid/invalid, exit code, BOM, CRLF, file kosong |
| `tests/test_robustness.py` | regresi bug hasil fuzzing, 2000 model acak, 3000 input sampah |

## Limitations

- Hanya association `-->` (searah, field dibuat di sisi sumber). Belum ada aggregation, composition, dependency, realization.
- Satu parent per class (`extends`); belum ada multiple inheritance, generics, atau tipe koleksi seperti `list[int]` pada atribut.
- Belum ada penanda `static`, method abstract individual, atau nilai default atribut. Pada abstract class dan interface, semua method menjadi `@abstractmethod`, sehingga class konkret harus mendeklarasikan ulang method tersebut agar bisa diinstansiasi.
- Overloading method tidak didukung (nama method yang sama dianggap duplikat).
- `-` (private) dan `#` (protected) sama-sama menjadi prefix `_` tanpa name mangling.
- Analyzer tidak memeriksa apakah class konkret sudah mengimplementasikan semua method interface, dan tidak memeriksa bentrok nama field asosiasi dengan atribut atau method warisan.
- Identifier hanya ASCII; komentar hanya `//`.
- Parser berhenti di syntax error pertama (tanpa error recovery).

## Roadmap

1. Composition, aggregation, dependency, dan realization (`*--`, `o--`, `..>`, `..|>`).
2. Penanda `abstract` dan `static` per method, serta nilai default atribut.
3. Tipe generik dan koleksi (`list[int]`, `dict[str, int]`).
4. Opsi keluaran `@dataclass` dan type hint `typing` untuk Python lama.
5. Error recovery di parser agar beberapa syntax error bisa dilaporkan sekaligus.
6. Peringatan semantic untuk interface yang belum diimplementasikan.
7. Antarmuka lain (GUI/web) di atas compiler core yang sama.
