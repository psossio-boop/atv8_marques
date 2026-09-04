import sys
import re
import sqlite3
import urllib.request
import urllib.error
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFormLayout, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QVBoxLayout, QWidget
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "cadastro.db"


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

    def fechar(self):
        self.connection.close()


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


class CadastroWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database()

        self.setWindowTitle("Cadastro de Pessoa")
        self.setMinimumSize(850, 650)

        self.criar_interface()
        self.aplicar_estilo()

    def criar_interface(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout_principal = QVBoxLayout(central)
        layout_principal.setContentsMargins(28, 24, 28, 24)
        layout_principal.setSpacing(18)

        titulo = QLabel("Cadastro de Pessoa")
        titulo.setObjectName("titulo")

        subtitulo = QLabel(
            "Preencha os dados abaixo. O CEP pode ser consultado automaticamente."
        )
        subtitulo.setObjectName("subtitulo")

        layout_principal.addWidget(titulo)
        layout_principal.addWidget(subtitulo)

        grupo_pessoal = QGroupBox("Dados pessoais e contato")
        grid_pessoal = QGridLayout(grupo_pessoal)
        grid_pessoal.setHorizontalSpacing(14)
        grid_pessoal.setVerticalSpacing(12)

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

        grid_pessoal.addWidget(QLabel("Nome completo *"), 0, 0)
        grid_pessoal.addWidget(self.nome, 0, 1, 1, 3)
        grid_pessoal.addWidget(QLabel("Tipo *"), 1, 0)
        grid_pessoal.addWidget(self.tipo_documento, 1, 1)
        grid_pessoal.addWidget(QLabel("CPF/CNPJ *"), 1, 2)
        grid_pessoal.addWidget(self.documento, 1, 3)
        grid_pessoal.addWidget(QLabel("E-mail *"), 2, 0)
        grid_pessoal.addWidget(self.email, 2, 1, 1, 3)
        grid_pessoal.addWidget(QLabel("Celular *"), 3, 0)
        grid_pessoal.addWidget(self.celular, 3, 1)

        layout_principal.addWidget(grupo_pessoal)

        grupo_endereco = QGroupBox("Endereço")
        grid_endereco = QGridLayout(grupo_endereco)
        grid_endereco.setHorizontalSpacing(14)
        grid_endereco.setVerticalSpacing(12)

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

        grid_endereco.addWidget(QLabel("CEP *"), 0, 0)
        grid_endereco.addWidget(self.cep, 0, 1)
        grid_endereco.addWidget(self.btn_cep, 0, 2)
        grid_endereco.addWidget(QLabel("Número *"), 0, 3)
        grid_endereco.addWidget(self.numero, 0, 4)

        grid_endereco.addWidget(QLabel("Logradouro *"), 1, 0)
        grid_endereco.addWidget(self.logradouro, 1, 1, 1, 4)

        grid_endereco.addWidget(QLabel("Complemento"), 2, 0)
        grid_endereco.addWidget(self.complemento, 2, 1, 1, 4)

        grid_endereco.addWidget(QLabel("Bairro *"), 3, 0)
        grid_endereco.addWidget(self.bairro, 3, 1, 1, 2)
        grid_endereco.addWidget(QLabel("Estado *"), 3, 3)
        grid_endereco.addWidget(self.estado, 3, 4)

        grid_endereco.addWidget(QLabel("Cidade *"), 4, 0)
        grid_endereco.addWidget(self.cidade, 4, 1, 1, 4)

        layout_principal.addWidget(grupo_endereco)

        botoes = QHBoxLayout()
        botoes.addStretch()

        self.btn_limpar = QPushButton("Limpar")
        self.btn_limpar.clicked.connect(self.limpar_formulario)

        self.btn_cadastrar = QPushButton("Cadastrar")
        self.btn_cadastrar.setObjectName("btnCadastrar")
        self.btn_cadastrar.clicked.connect(self.cadastrar)

        botoes.addWidget(self.btn_limpar)
        botoes.addWidget(self.btn_cadastrar)

        layout_principal.addLayout(botoes)

        rodape = QLabel("* Campos obrigatórios")
        rodape.setObjectName("rodape")
        layout_principal.addWidget(rodape)

        self.nome.setFocus()

    def aplicar_estilo(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #f5f7fb;
                color: #1f2937;
                font-size: 14px;
            }

            #titulo {
                font-size: 28px;
                font-weight: 700;
                color: #111827;
            }

            #subtitulo, #rodape {
                color: #6b7280;
            }

            QGroupBox {
                background: white;
                border: 1px solid #dbe1ea;
                border-radius: 10px;
                margin-top: 10px;
                padding: 18px;
                font-weight: 700;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                background: #f5f7fb;
            }

            QLineEdit, QComboBox {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 7px;
                padding: 9px;
                min-height: 20px;
            }

            QLineEdit:focus, QComboBox:focus {
                border: 2px solid #4f46e5;
            }

            QPushButton {
                border: 1px solid #cbd5e1;
                border-radius: 7px;
                padding: 10px 18px;
                background: white;
                font-weight: 600;
            }

            QPushButton:hover {
                background: #eef2ff;
            }

            #btnCadastrar {
                background: #4f46e5;
                color: white;
                border: none;
            }

            #btnCadastrar:hover {
                background: #4338ca;
            }
        """)

    def atualizar_documento(self):
        self.documento.clear()
        tipo = self.tipo_documento.currentText()
        self.documento.setPlaceholderText(
            "Digite o CPF" if tipo == "CPF" else "Digite o CNPJ"
        )

    def formatar_documento(self):
        texto = apenas_digitos(self.documento.text())
        cursor = self.documento.cursorPosition()

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

    def consultar_cep(self):
        cep = apenas_digitos(self.cep.text())

        if len(cep) != 8:
            QMessageBox.warning(
                self, "CEP inválido",
                "O CEP deve conter exatamente 8 números.\n"
                "Exemplo: 01001-000."
            )
            return

        self.btn_cep.setEnabled(False)
        self.btn_cep.setText("Consultando...")

        QApplication.setOverrideCursor(Qt.WaitCursor)

        try:
            url = f"https://viacep.com.br/ws/{cep}/json/"
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "CadastroPySide6/1.0"}
            )

            with urllib.request.urlopen(request, timeout=8) as resposta:
                if resposta.status != 200:
                    raise ConnectionError("O serviço retornou um status inesperado.")

                dados = json.loads(resposta.read().decode("utf-8"))

            if dados.get("erro"):
                QMessageBox.warning(
                    self, "CEP não encontrado",
                    "O CEP informado não foi encontrado.\n"
                    "Confira os números e tente novamente."
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
                "Não foi possível consultar o CEP.\n\n"
                "Verifique sua conexão com a internet e tente novamente."
            )
        except (TimeoutError, ConnectionError):
            QMessageBox.critical(
                self, "Serviço indisponível",
                "O serviço de consulta de CEP não respondeu no tempo esperado.\n"
                "Tente novamente mais tarde."
            )
        except (json.JSONDecodeError, ValueError):
            QMessageBox.critical(
                self, "Resposta inválida",
                "O serviço retornou uma resposta que não pôde ser interpretada."
            )
        except Exception as erro:
            QMessageBox.critical(
                self, "Erro inesperado",
                f"Não foi possível realizar a consulta.\n\nDetalhes: {erro}"
            )
        finally:
            QApplication.restoreOverrideCursor()
            self.btn_cep.setEnabled(True)
            self.btn_cep.setText("Consultar CEP")

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
        tipo = self.tipo_documento.currentText()

        if tipo == "CPF":
            if not validar_cpf(doc_digitos):
                erros.append("• O CPF informado não é válido.")
        else:
            if not validar_cnpj(doc_digitos):
                erros.append("• O CNPJ informado não é válido.")

        if not email:
            erros.append("• Informe o e-mail.")
        elif not email_valido(email):
            erros.append("• O e-mail não possui um formato válido. Exemplo: nome@email.com.")

        if not celular:
            erros.append("• Informe o número de celular.")
        elif not celular_valido(celular):
            erros.append("• O celular deve possuir DDD e 8 ou 9 dígitos.")

        if not cep_valido(cep):
            erros.append("• O CEP deve conter exatamente 8 números.")

        if not logradouro:
            erros.append("• Informe o logradouro. Consulte o CEP para preenchê-lo automaticamente.")
        if not numero:
            erros.append("• Informe o número do endereço.")
        if not bairro:
            erros.append("• Informe o bairro.")
        if not cidade:
            erros.append("• Informe a cidade.")
        if not estado:
            erros.append("• Selecione o estado.")

        return erros

    def cadastrar(self):
        erros = self.validar_dados()

        if erros:
            QMessageBox.warning(
                self, "Corrija os dados",
                "Não foi possível realizar o cadastro:\n\n" +
                "\n".join(erros)
            )
            return

        dados = {
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
            "estado": self.estado.currentData()
        }

        try:
            self.db.inserir(dados)
            QMessageBox.information(
                self, "Cadastro realizado",
                f"Cadastro de {dados['nome']} realizado com sucesso!\n\n"
                "Os dados foram salvos no banco SQLite."
            )
            self.limpar_formulario()
        except sqlite3.Error as erro:
            QMessageBox.critical(
                self, "Erro no banco de dados",
                f"Não foi possível salvar o cadastro.\n\nDetalhes: {erro}"
            )

    def limpar_formulario(self):
        self.nome.clear()
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
        self.tipo_documento.setCurrentIndex(0)
        self.nome.setFocus()

    def closeEvent(self, event):
        self.db.fechar()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Cadastro de Pessoa - PySide6")
    janela = CadastroWindow()
    janela.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
