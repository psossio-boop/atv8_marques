import sys
import re
import sqlite3
import urllib.request
import urllib.error
import json
from pathlib import Path

from PySide6.QtCore import Qt, QMarginsF
from PySide6.QtGui import QIntValidator, QPdfWriter, QPageSize, QTextDocument
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QSplitter, QScrollArea, QFrame
)

# ---------- Local onde o banco será salvo (fora da pasta do projeto) ----------
DB_DIR = Path.home() / ".cadastro_app"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "cadastro.db"


# ---------------------------------------------------------------- BANCO
class Database:
    def __init__(self, db_path=DB_PATH):
        self.connection = sqlite3.connect(db_path)
        self.create_table()

    def create_table(self):
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS pessoas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_documento TEXT NOT NULL,
                documento TEXT NOT NULL,
                nome TEXT NOT NULL,
                email TEXT NOT NULL,
                celular TEXT NOT NULL,
                cep TEXT NOT NULL,
                logradouro TEXT NOT NULL,
                numero TEXT NOT NULL,
                complemento TEXT,
                bairro TEXT NOT NULL,
                cidade TEXT NOT NULL,
                estado TEXT NOT NULL,
                criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.connection.commit()

    # CREATE
    def inserir(self, dados):
        self.connection.execute("""
            INSERT INTO pessoas (
                tipo_documento, documento, nome, email, celular, cep,
                logradouro, numero, complemento, bairro, cidade, estado
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dados["tipo_documento"], dados["documento"], dados["nome"],
            dados["email"], dados["celular"], dados["cep"],
            dados["logradouro"], dados["numero"], dados["complemento"],
            dados["bairro"], dados["cidade"], dados["estado"]
        ))
        self.connection.commit()

    # READ (lista com filtro opcional)
    def listar(self, filtro=""):
        sql = """
            SELECT id, nome, tipo_documento, documento, email, celular, cidade, estado
            FROM pessoas
        """
        params = ()
        if filtro:
            termo = f"%{filtro}%"
            sql += """
                WHERE nome LIKE ?
                   OR documento LIKE ?
                   OR email LIKE ?
                   OR cidade LIKE ?
                   OR estado LIKE ?
                   OR celular LIKE ?
            """
            params = (termo, termo, termo, termo, termo, termo)
        sql += " ORDER BY id DESC"
        return self.connection.execute(sql, params).fetchall()

    def buscar_por_id(self, id_registro):
        return self.connection.execute("""
            SELECT id, tipo_documento, documento, nome, email, celular, cep,
                   logradouro, numero, complemento, bairro, cidade, estado
            FROM pessoas WHERE id = ?
        """, (id_registro,)).fetchone()

    # UPDATE
    def atualizar(self, id_registro, dados):
        self.connection.execute("""
            UPDATE pessoas SET
                tipo_documento = ?, documento = ?, nome = ?, email = ?,
                celular = ?, cep = ?, logradouro = ?, numero = ?,
                complemento = ?, bairro = ?, cidade = ?, estado = ?
            WHERE id = ?
        """, (
            dados["tipo_documento"], dados["documento"], dados["nome"],
            dados["email"], dados["celular"], dados["cep"],
            dados["logradouro"], dados["numero"], dados["complemento"],
            dados["bairro"], dados["cidade"], dados["estado"],
            id_registro
        ))
        self.connection.commit()

    # DELETE
    def excluir(self, id_registro):
        self.connection.execute("DELETE FROM pessoas WHERE id = ?", (id_registro,))
        self.connection.commit()

    def fechar(self):
        self.connection.close()


# ------------------------------------------------------------ VALIDAÇÕES
def apenas_digitos(valor):
    return re.sub(r"\D", "", valor)


def validar_cpf(cpf):
    cpf = apenas_digitos(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    digito1 = (soma * 10) % 11
    if digito1 == 10:
        digito1 = 0
    if digito1 != int(cpf[9]):
        return False
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    digito2 = (soma * 10) % 11
    if digito2 == 10:
        digito2 = 0
    return digito2 == int(cpf[10])


def validar_cnpj(cnpj):
    cnpj = apenas_digitos(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto
    if digito1 != int(cnpj[12]):
        return False
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto
    return digito2 == int(cnpj[13])


def email_valido(email):
    return re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", email) is not None


def celular_valido(celular):
    numero = apenas_digitos(celular)
    return len(numero) in (10, 11) and numero[2] not in ("0", "1")


def cep_valido(cep):
    return len(apenas_digitos(cep)) == 8


# --------------------------------------------------------------- JANELA
class CadastroWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.id_edicao = None

        self.setWindowTitle("Cadastro de Pessoa")
        self.setMinimumSize(1050, 780)

        self.criar_interface()
        self.aplicar_estilo()
        self.carregar_tabela()

    # ------------------------------------------------------------ UI
    def criar_interface(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout_principal = QVBoxLayout(central)
        layout_principal.setContentsMargins(24, 20, 24, 20)
        layout_principal.setSpacing(12)

        titulo = QLabel("Cadastro de Pessoa")
        titulo.setObjectName("titulo")
        subtitulo = QLabel(
            "Preencha os dados, consulte o CEP e gerencie os cadastros na tabela abaixo."
        )
        subtitulo.setObjectName("subtitulo")
        layout_principal.addWidget(titulo)
        layout_principal.addWidget(subtitulo)

        splitter = QSplitter(Qt.Vertical)
        layout_principal.addWidget(splitter, 1)

        # ---------------- TOPO: formulário dentro de scroll ----------------
        topo = QWidget()
        topo_layout = QVBoxLayout(topo)
        topo_layout.setContentsMargins(0, 0, 0, 0)
        topo_layout.setSpacing(14)

        grupo_pessoal = self._criar_grupo_pessoal()
        grupo_endereco = self._criar_grupo_endereco()

        topo_layout.addWidget(grupo_pessoal)
        topo_layout.addWidget(grupo_endereco)
        topo_layout.addLayout(self._criar_botoes_acao())
        topo_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(topo)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        splitter.addWidget(scroll)

        # ---------------- BASE: filtro + tabela ----------------
        base = QWidget()
        base_layout = QVBoxLayout(base)
        base_layout.setContentsMargins(0, 0, 0, 0)
        base_layout.setSpacing(10)

        filtro_row = QHBoxLayout()
        filtro_row.addWidget(QLabel("Filtrar:"))
        self.filtro = QLineEdit()
        self.filtro.setPlaceholderText("Digite nome, CPF/CNPJ, e-mail, cidade ou UF...")
        self.filtro.setClearButtonEnabled(True)
        self.filtro.textChanged.connect(self.carregar_tabela)
        filtro_row.addWidget(self.filtro, 1)

        self.btn_exportar = QPushButton("Exportar PDF")
        self.btn_exportar.setObjectName("btnExportar")
        self.btn_exportar.clicked.connect(self.exportar_pdf)
        filtro_row.addWidget(self.btn_exportar)

        base_layout.addLayout(filtro_row)

        self.tabela = QTableWidget()
        self.tabela.setColumnCount(8)
        self.tabela.setHorizontalHeaderLabels(
            ["ID", "Nome", "Tipo", "Documento", "E-mail", "Celular", "Cidade", "Estado"]
        )
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.verticalHeader().setVisible(False)
        header = self.tabela.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        for i in (0, 2, 3, 5, 6, 7):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.tabela.itemSelectionChanged.connect(self.carregar_selecionado)

        base_layout.addWidget(self.tabela, 1)
        splitter.addWidget(base)
        splitter.setSizes([430, 320])

        rodape = QLabel("* Campos obrigatórios — clique em uma linha da tabela para editar.")
        rodape.setObjectName("rodape")
        layout_principal.addWidget(rodape)

        self.nome.setFocus()

    def _criar_grupo_pessoal(self):
        grupo = QGroupBox("Dados pessoais e contato")
        grid = QGridLayout(grupo)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)

        self.nome = QLineEdit()
        self.nome.setPlaceholderText("Nome completo")

        self.tipo_documento = QComboBox()
        self.tipo_documento.addItems(["CPF", "CNPJ"])
        self.tipo_documento.currentTextChanged.connect(self.atualizar_documento)

        self.documento = QLineEdit()
        self.documento.setPlaceholderText("Digite o CPF")
        self.documento.textChanged.connect(self.formatar_documento)

        self.email = QLineEdit()
        self.email.setPlaceholderText("exemplo@email.com")

        self.celular = QLineEdit()
        self.celular.setPlaceholderText("(11) 99999-9999")
        self.celular.textChanged.connect(self.formatar_celular)

        grid.addWidget(QLabel("Nome completo *"), 0, 0)
        grid.addWidget(self.nome, 0, 1, 1, 3)
        grid.addWidget(QLabel("Tipo *"), 1, 0)
        grid.addWidget(self.tipo_documento, 1, 1)
        grid.addWidget(QLabel("CPF/CNPJ *"), 1, 2)
        grid.addWidget(self.documento, 1, 3)
        grid.addWidget(QLabel("E-mail *"), 2, 0)
        grid.addWidget(self.email, 2, 1, 1, 3)
        grid.addWidget(QLabel("Celular *"), 3, 0)
        grid.addWidget(self.celular, 3, 1)
        return grupo

    def _criar_grupo_endereco(self):
        grupo = QGroupBox("Endereço")
        grid = QGridLayout(grupo)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)

        self.cep = QLineEdit()
        self.cep.setPlaceholderText("00000-000")
        self.cep.textChanged.connect(self.formatar_cep)

        self.btn_cep = QPushButton("Consultar CEP")
        self.btn_cep.clicked.connect(self.consultar_cep)

        self.logradouro = QLineEdit()
        self.numero = QLineEdit()
        self.numero.setValidator(QIntValidator(0, 999999))
        self.complemento = QLineEdit()
        self.bairro = QLineEdit()
        self.cidade = QLineEdit()

        self.estado = QComboBox()
        estados = [
            ("AC", "Acre"), ("AL", "Alagoas"), ("AP", "Amapá"),
            ("AM", "Amazonas"), ("BA", "Bahia"), ("CE", "Ceará"),
            ("DF", "Distrito Federal"), ("ES", "Espírito Santo"),
            ("GO", "Goiás"), ("MA", "Maranhão"), ("MT", "Mato Grosso"),
            ("MS", "Mato Grosso do Sul"), ("MG", "Minas Gerais"),
            ("PA", "Pará"), ("PB", "Paraíba"), ("PR", "Paraná"),
            ("PE", "Pernambuco"), ("PI", "Piauí"), ("RJ", "Rio de Janeiro"),
            ("RN", "Rio Grande do Norte"), ("RS", "Rio Grande do Sul"),
            ("RO", "Rondônia"), ("RR", "Roraima"), ("SC", "Santa Catarina"),
            ("SP", "São Paulo"), ("SE", "Sergipe"), ("TO", "Tocantins")
        ]
        self.estado.addItem("Selecione...", "")
        for sigla, nome in estados:
            self.estado.addItem(f"{sigla} - {nome}", sigla)

        grid.addWidget(QLabel("CEP *"), 0, 0)
        grid.addWidget(self.cep, 0, 1)
        grid.addWidget(self.btn_cep, 0, 2)
        grid.addWidget(QLabel("Número *"), 0, 3)
        grid.addWidget(self.numero, 0, 4)

        grid.addWidget(QLabel("Logradouro *"), 1, 0)
        grid.addWidget(self.logradouro, 1, 1, 1, 4)

        grid.addWidget(QLabel("Complemento"), 2, 0)
        grid.addWidget(self.complemento, 2, 1, 1, 4)

        grid.addWidget(QLabel("Bairro *"), 3, 0)
        grid.addWidget(self.bairro, 3, 1, 1, 2)
        grid.addWidget(QLabel("Estado *"), 3, 3)
        grid.addWidget(self.estado, 3, 4)

        grid.addWidget(QLabel("Cidade *"), 4, 0)
        grid.addWidget(self.cidade, 4, 1, 1, 4)
        return grupo

    def _criar_botoes_acao(self):
        botoes = QHBoxLayout()
        botoes.addStretch()

        self.btn_limpar = QPushButton("Novo / Limpar")
        self.btn_limpar.clicked.connect(self.limpar_formulario)

        self.btn_cadastrar = QPushButton("Cadastrar")
        self.btn_cadastrar.setObjectName("btnCadastrar")
        self.btn_cadastrar.clicked.connect(self.cadastrar)

        self.btn_atualizar = QPushButton("Atualizar")
        self.btn_atualizar.setObjectName("btnAtualizar")
        self.btn_atualizar.clicked.connect(self.atualizar)
        self.btn_atualizar.setEnabled(False)

        self.btn_excluir = QPushButton("Excluir")
        self.btn_excluir.setObjectName("btnExcluir")
        self.btn_excluir.clicked.connect(self.excluir)
        self.btn_excluir.setEnabled(False)

        botoes.addWidget(self.btn_limpar)
        botoes.addWidget(self.btn_cadastrar)
        botoes.addWidget(self.btn_atualizar)
        botoes.addWidget(self.btn_excluir)
        return botoes

    def aplicar_estilo(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #f5f7fb;
                color: #1f2937;
                font-size: 14px;
            }
            #titulo { font-size: 26px; font-weight: 700; color: #111827; }
            #subtitulo, #rodape { color: #6b7280; }

            QGroupBox {
                background: white;
                border: 1px solid #dbe1ea;
                border-radius: 10px;
                margin-top: 10px;
                padding: 18px;
                font-weight: 700;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 14px;
                padding: 0 6px; background: #f5f7fb;
            }

            QLineEdit, QComboBox {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 7px;
                padding: 8px;
                min-height: 20px;
            }
            QLineEdit:focus, QComboBox:focus { border: 2px solid #4f46e5; }

            QPushButton {
                border: 1px solid #cbd5e1;
                border-radius: 7px;
                padding: 9px 16px;
                background: white;
                font-weight: 600;
            }
            QPushButton:hover { background: #eef2ff; }
            QPushButton:disabled { color: #9ca3af; background: #f3f4f6; }

            #btnCadastrar { background: #4f46e5; color: white; border: none; }
            #btnCadastrar:hover { background: #4338ca; }

            #btnAtualizar { background: #0ea5e9; color: white; border: none; }
            #btnAtualizar:hover { background: #0284c7; }
            #btnAtualizar:disabled { background: #cbd5e1; color: #6b7280; }

            #btnExcluir { background: #ef4444; color: white; border: none; }
            #btnExcluir:hover { background: #dc2626; }
            #btnExcluir:disabled { background: #cbd5e1; color: #6b7280; }

            #btnExportar { background: #16a34a; color: white; border: none; }
            #btnExportar:hover { background: #15803d; }

            QTableWidget {
                background: white;
                border: 1px solid #dbe1ea;
                border-radius: 10px;
                gridline-color: #e5e7eb;
                alternate-background-color: #f9fafb;
            }
            QTableWidget::item { padding: 4px; }
            QTableWidget::item:selected {
                background: #c7d2fe; color: #111827;
            }
            QHeaderView::section {
                background: #4f46e5; color: white;
                padding: 8px; border: none; font-weight: 600;
            }
        """)

    # ------------------------------------------------- formatação de campos
    def atualizar_documento(self):
        self.documento.clear()
        tipo = self.tipo_documento.currentText()
        self.documento.setPlaceholderText(
            "Digite o CPF" if tipo == "CPF" else "Digite o CNPJ"
        )

    def formatar_documento(self):
        texto = apenas_digitos(self.documento.text())
        if self.tipo_documento.currentText() == "CPF":
            texto = texto[:11]
            if len(texto) > 9:
                texto = f"{texto[:3]}.{texto[3:6]}.{texto[6:9]}-{texto[9:]}"
            elif len(texto) > 6:
                texto = f"{texto[:3]}.{texto[3:6]}.{texto[6:]}"
            elif len(texto) > 3:
                texto = f"{texto[:3]}.{texto[3:]}"
        else:
            texto = texto[:14]
            if len(texto) > 12:
                texto = f"{texto[:2]}.{texto[2:5]}.{texto[5:8]}/{texto[8:12]}-{texto[12:]}"
            elif len(texto) > 8:
                texto = f"{texto[:2]}.{texto[2:5]}.{texto[5:8]}/{texto[8:]}"
            elif len(texto) > 5:
                texto = f"{texto[:2]}.{texto[2:5]}.{texto[5:]}"
            elif len(texto) > 2:
                texto = f"{texto[:2]}.{texto[2:]}"

        if texto != self.documento.text():
            self.documento.blockSignals(True)
            self.documento.setText(texto)
            self.documento.setCursorPosition(len(texto))
            self.documento.blockSignals(False)

    def formatar_celular(self):
        texto = apenas_digitos(self.celular.text())[:11]
        if len(texto) > 7:
            texto = f"({texto[:2]}) {texto[2:7]}-{texto[7:]}"
        elif len(texto) > 2:
            texto = f"({texto[:2]}) {texto[2:]}"
        if texto != self.celular.text():
            self.celular.blockSignals(True)
            self.celular.setText(texto)
            self.celular.setCursorPosition(len(texto))
            self.celular.blockSignals(False)

    def formatar_cep(self):
        texto = apenas_digitos(self.cep.text())[:8]
        if len(texto) > 5:
            texto = f"{texto[:5]}-{texto[5:]}"
        if texto != self.cep.text():
            self.cep.blockSignals(True)
            self.cep.setText(texto)
            self.cep.setCursorPosition(len(texto))
            self.cep.blockSignals(False)

    # ------------------------------------------------------------ ViaCEP
    def consultar_cep(self):
        cep = apenas_digitos(self.cep.text())
        if len(cep) != 8:
            QMessageBox.warning(
                self, "CEP inválido",
                "O CEP deve conter exatamente 8 números.\nExemplo: 01001-000."
            )
            return

        self.btn_cep.setEnabled(False)
        self.btn_cep.setText("Consultando...")
        QApplication.setOverrideCursor(Qt.WaitCursor)

        try:
            url = f"https://viacep.com.br/ws/{cep}/json/"
            request = urllib.request.Request(
                url, headers={"User-Agent": "CadastroPySide6/1.0"}
            )
            with urllib.request.urlopen(request, timeout=8) as resposta:
                if resposta.status != 200:
                    raise ConnectionError("Status inesperado.")
                dados = json.loads(resposta.read().decode("utf-8"))

            if dados.get("erro"):
                QMessageBox.warning(
                    self, "CEP não encontrado",
                    "O CEP informado não foi encontrado."
                )
                return

            self.logradouro.setText(dados.get("logradouro", ""))
            self.bairro.setText(dados.get("bairro", ""))
            self.cidade.setText(dados.get("localidade", ""))

            uf = dados.get("uf", "")
            indice = self.estado.findData(uf)
            if indice >= 0:
                self.estado.setCurrentIndex(indice)

            QMessageBox.information(
                self, "Consulta realizada",
                "Endereço encontrado e preenchido automaticamente."
            )
        except urllib.error.URLError:
            QMessageBox.critical(
                self, "Erro de conexão",
                "Não foi possível consultar o CEP.\nVerifique sua internet."
            )
        except (TimeoutError, ConnectionError):
            QMessageBox.critical(
                self, "Serviço indisponível",
                "O serviço de CEP não respondeu no tempo esperado."
            )
        except (json.JSONDecodeError, ValueError):
            QMessageBox.critical(
                self, "Resposta inválida",
                "O serviço retornou uma resposta inválida."
            )
        except Exception as erro:
            QMessageBox.critical(
                self, "Erro inesperado", f"Detalhes: {erro}"
            )
        finally:
            QApplication.restoreOverrideCursor()
            self.btn_cep.setEnabled(True)
            self.btn_cep.setText("Consultar CEP")

    # ----------------------------------------------------------- validação
    def validar_dados(self):
        erros = []
        nome = self.nome.text().strip()
        documento = self.documento.text().strip()
        email = self.email.text().strip()
        celular = self.celular.text().strip()
        cep = self.cep.text().strip()
        logradouro = self.logradouro.text().strip()
        numero = self.numero.text().strip()
        bairro = self.bairro.text().strip()
        cidade = self.cidade.text().strip()
        estado = self.estado.currentData()

        if not nome:
            erros.append("• Informe o nome completo.")
        elif len(nome.split()) < 2:
            erros.append("• Informe nome e sobrenome.")

        doc_digitos = apenas_digitos(documento)
        if self.tipo_documento.currentText() == "CPF":
            if not validar_cpf(doc_digitos):
                erros.append("• O CPF informado não é válido.")
        else:
            if not validar_cnpj(doc_digitos):
                erros.append("• O CNPJ informado não é válido.")

        if not email:
            erros.append("• Informe o e-mail.")
        elif not email_valido(email):
            erros.append("• E-mail inválido. Exemplo: nome@email.com.")

        if not celular:
            erros.append("• Informe o número de celular.")
        elif not celular_valido(celular):
            erros.append("• O celular deve possuir DDD e 8 ou 9 dígitos.")

        if not cep_valido(cep):
            erros.append("• O CEP deve conter exatamente 8 números.")
        if not logradouro:
            erros.append("• Informe o logradouro.")
        if not numero:
            erros.append("• Informe o número do endereço.")
        if not bairro:
            erros.append("• Informe o bairro.")
        if not cidade:
            erros.append("• Informe a cidade.")
        if not estado:
            erros.append("• Selecione o estado.")
        return erros

    def _coletar_dados(self):
        return {
            "tipo_documento": self.tipo_documento.currentText(),
            "documento": apenas_digitos(self.documento.text()),
            "nome": self.nome.text().strip(),
            "email": self.email.text().strip(),
            "celular": apenas_digitos(self.celular.text()),
            "cep": apenas_digitos(self.cep.text()),
            "logradouro": self.logradouro.text().strip(),
            "numero": self.numero.text().strip(),
            "complemento": self.complemento.text().strip(),
            "bairro": self.bairro.text().strip(),
            "cidade": self.cidade.text().strip(),
            "estado": self.estado.currentData(),
        }

    # ------------------------------------------------------------- CRUD
    def cadastrar(self):
        if self.id_edicao is not None:
            QMessageBox.information(
                self, "Modo edição",
                "Você está editando um registro existente.\n"
                "Use 'Atualizar' ou 'Novo / Limpar' antes de cadastrar."
            )
            return

        erros = self.validar_dados()
        if erros:
            QMessageBox.warning(
                self, "Corrija os dados",
                "Não foi possível realizar o cadastro:\n\n" + "\n".join(erros)
            )
            return

        dados = self._coletar_dados()
        try:
            self.db.inserir(dados)
            QMessageBox.information(
                self, "Cadastro realizado",
                f"Cadastro de {dados['nome']} realizado com sucesso!"
            )
            self.limpar_formulario()
            self.carregar_tabela()
        except sqlite3.Error as erro:
            QMessageBox.critical(
                self, "Erro no banco",
                f"Não foi possível salvar.\n\nDetalhes: {erro}"
            )

    def carregar_tabela(self):
        filtro = self.filtro.text().strip() if hasattr(self, "filtro") else ""
        registros = self.db.listar(filtro)

        self.tabela.blockSignals(True)
        self.tabela.setRowCount(0)
        for linha, registro in enumerate(registros):
            self.tabela.insertRow(linha)
            for coluna, valor in enumerate(registro):
                self.tabela.setItem(linha, coluna, QTableWidgetItem(str(valor)))
        self.tabela.blockSignals(False)

        if self.id_edicao is None:
            self.btn_atualizar.setEnabled(False)
            self.btn_excluir.setEnabled(False)

    def carregar_selecionado(self):
        itens = self.tabela.selectedItems()
        if not itens:
            self.id_edicao = None
            self.btn_atualizar.setEnabled(False)
            self.btn_excluir.setEnabled(False)
            return

        linha = itens[0].row()
        id_registro = int(self.tabela.item(linha, 0).text())
        registro = self.db.buscar_por_id(id_registro)
        if not registro:
            return

        self.id_edicao = id_registro

        self.tipo_documento.blockSignals(True)
        self.documento.blockSignals(True)
        self.celular.blockSignals(True)
        self.cep.blockSignals(True)

        self.tipo_documento.setCurrentText(registro[1])
        self.documento.setText(registro[2])
        self.nome.setText(registro[3])
        self.email.setText(registro[4])
        self.celular.setText(registro[5])
        self.cep.setText(registro[6])
        self.logradouro.setText(registro[7])
        self.numero.setText(registro[8])
        self.complemento.setText(registro[9] or "")
        self.bairro.setText(registro[10])
        self.cidade.setText(registro[11])
        indice = self.estado.findData(registro[12])
        if indice >= 0:
            self.estado.setCurrentIndex(indice)

        self.tipo_documento.blockSignals(False)
        self.documento.blockSignals(False)
        self.celular.blockSignals(False)
        self.cep.blockSignals(False)

        self.formatar_documento()
        self.formatar_celular()
        self.formatar_cep()

        self.btn_atualizar.setEnabled(True)
        self.btn_excluir.setEnabled(True)

    def atualizar(self):
        if self.id_edicao is None:
            QMessageBox.warning(
                self, "Nenhum registro",
                "Selecione um registro na tabela para atualizar."
            )
            return

        erros = self.validar_dados()
        if erros:
            QMessageBox.warning(
                self, "Corrija os dados",
                "Não foi possível atualizar:\n\n" + "\n".join(erros)
            )
            return

        dados = self._coletar_dados()
        try:
            self.db.atualizar(self.id_edicao, dados)
            QMessageBox.information(
                self, "Atualizado",
                f"Cadastro de {dados['nome']} atualizado com sucesso!"
            )
            self.limpar_formulario()
            self.carregar_tabela()
        except sqlite3.Error as erro:
            QMessageBox.critical(
                self, "Erro no banco",
                f"Não foi possível atualizar.\n\nDetalhes: {erro}"
            )

    def excluir(self):
        if self.id_edicao is None:
            QMessageBox.warning(
                self, "Nenhum registro",
                "Selecione um registro na tabela para excluir."
            )
            return

        resposta = QMessageBox.question(
            self, "Confirmar exclusão",
            f"Tem certeza que deseja excluir o registro de\n"
            f"'{self.nome.text()}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if resposta != QMessageBox.Yes:
            return

        try:
            self.db.excluir(self.id_edicao)
            QMessageBox.information(self, "Excluído", "Registro excluído com sucesso!")
            self.limpar_formulario()
            self.carregar_tabela()
        except sqlite3.Error as erro:
            QMessageBox.critical(
                self, "Erro no banco",
                f"Não foi possível excluir.\n\nDetalhes: {erro}"
            )

    # ----------------------------------------------------- Exportar PDF
    def exportar_pdf(self):
        if self.tabela.rowCount() == 0:
            QMessageBox.warning(
                self, "Sem dados",
                "Não há registros visíveis na tabela para exportar."
            )
            return

        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar PDF", "cadastros.pdf", "Arquivo PDF (*.pdf)"
        )
        if not caminho:
            return
        if not caminho.lower().endswith(".pdf"):
            caminho += ".pdf"

        try:
            writer = QPdfWriter(caminho)
            writer.setPageSize(QPageSize(QPageSize.A4))
            writer.setPageMargins(QMarginsF(15, 15, 15, 15))
            writer.setResolution(300)
            writer.setTitle("Lista de Cadastros")

            doc = QTextDocument()
            doc.setHtml(self._montar_html_pdf())
            doc.print_(writer)

            QMessageBox.information(
                self, "PDF gerado",
                f"Arquivo salvo com sucesso em:\n{caminho}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Erro", f"Erro ao gerar PDF:\n{e}"
            )

    def _montar_html_pdf(self):
        colunas = [
            self.tabela.horizontalHeaderItem(i).text()
            for i in range(self.tabela.columnCount())
        ]
        linhas = []
        for r in range(self.tabela.rowCount()):
            linha = []
            for c in range(self.tabela.columnCount()):
                item = self.tabela.item(r, c)
                linha.append(item.text() if item else "")
            linhas.append(linha)

        filtro = self.filtro.text().strip()
        info_filtro = f" — filtro aplicado: <b>{filtro}</b>" if filtro else ""

        cabecalho = "".join(f"<th>{c}</th>" for c in colunas)
        corpo = "".join(
            "<tr>" + "".join(f"<td>{v}</td>" for v in linha) + "</tr>"
            for linha in linhas
        )

        return f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; color: #1f2937; }}
                h1 {{ color: #4f46e5; margin-bottom: 4px; }}
                p.sub {{ color: #6b7280; margin-top: 0; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
                th {{
                    background-color: #4f46e5; color: white;
                    padding: 6px; border: 1px solid #3730a3;
                    text-align: left; font-size: 10pt;
                }}
                td {{
                    padding: 5px; border: 1px solid #cbd5e1;
                    font-size: 9pt;
                }}
                tr:nth-child(even) td {{ background-color: #eef2ff; }}
            </style>
        </head>
        <body>
            <h1>Lista de Cadastros</h1>
            <p class="sub">
                Total de registros: <b>{len(linhas)}</b>{info_filtro}
            </p>
            <table>
                <thead><tr>{cabecalho}</tr></thead>
                <tbody>{corpo}</tbody>
            </table>
        </body>
        </html>
        """

    # ------------------------------------------------------------- limpar
    def limpar_formulario(self):
        self.id_edicao = None

        self.nome.clear()
        self.tipo_documento.setCurrentIndex(0)
        self.documento.clear()
        self.email.clear()
        self.celular.clear()
        self.cep.clear()
        self.logradouro.clear()
        self.numero.clear()
        self.complemento.clear()
        self.bairro.clear()
        self.cidade.clear()
        self.estado.setCurrentIndex(0)

        self.tabela.clearSelection()
        self.btn_atualizar.setEnabled(False)
        self.btn_excluir.setEnabled(False)
        self.nome.setFocus()

    def closeEvent(self, event):
        self.db.fechar()
        event.accept()


# ---------------------------------------------------------------- MAIN
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Cadastro de Pessoa - PySide6")
    janela = CadastroWindow()
    janela.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
