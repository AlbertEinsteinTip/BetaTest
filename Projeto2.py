import streamlit as st
import pandas as pd
import plotly.express as px
from ofxparse import OfxParser
import io
import os


openai_api_key = os.getenv("OPENAI_API_KEY")

def process_ofx(uploaded_file):
    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        try:
            file_text = file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            file_text = file_bytes.decode('latin1')

        file_stream = io.StringIO(file_text)
        ofx = OfxParser.parse(file_stream)

        transactions = []
        for account in ofx.accounts:
            for transaction in account.statement.transactions:
                transactions.append({
                    "Data": transaction.date.strftime("%Y-%m-%d"),
                    "Descrição": transaction.memo if transaction.memo else "Sem descrição",
                    "Valor": float(transaction.amount)
                })

        return pd.DataFrame(transactions)
    return pd.DataFrame()

def process_excel(uploaded_file):
    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file)
        # Converter a coluna "Valor" para float, se necessário
        df["Valor"] = df["Valor"].astype(float)
        return df
    return None

def compare_and_replace_vetor(ofx_df, excel_df):
    # Faz o merge dos DataFrames com base na coluna "Valor"
    merged_df = pd.merge(ofx_df, excel_df[['Valor', 'Descrição']], on="Valor", how="left", suffixes=("", "_excel"))
    # Atualiza a coluna "Descrição" quando houver valor na planilha Excel
    merged_df["Descrição"] = merged_df["Descrição_excel"].combine_first(merged_df["Descrição"])
    merged_df.drop(columns=["Descrição_excel"], inplace=True)
    return merged_df

# Interface com o usuário via Streamlit
st.title("Análise Financeira OFX")

file_ofx = st.file_uploader("Faça upload do seu arquivo OFX", type=["ofx"])
file_excel = st.file_uploader("Faça upload da sua planilha Excel", type=["xlsx"])

if file_ofx is not None:
    df_ofx = process_ofx(file_ofx)
    st.subheader("Dados Importados do OFX")
    st.write(df_ofx)

if file_excel is not None:
    df_excel = process_excel(file_excel)
    st.subheader("Dados Importados do Excel")
    st.write(df_excel)

if file_ofx is not None and file_excel is not None:
    df_ofx_atualizado = compare_and_replace_vetor(df_ofx, df_excel)
    st.subheader("OFX Atualizado com Descrições do Excel")
    st.write(df_ofx_atualizado)

    fig = px.pie(df_ofx_atualizado, names="Descrição", values="Valor", title="Distribuição dos Gastos Atualizada")
    st.plotly_chart(fig)


    def generate_ofx_content(df):
        # Cabeçalho básico do OFX
        header = """OFXHEADER:100
    DATA:OFXSGML
    VERSION:102
    SECURITY:NONE
    ENCODING:USASCII
    CHARSET:1252
    COMPRESSION:NONE
    OLDFILEUID:NONE
    NEWFILEUID:NONE

    <OFX>
    <SIGNONMSGSRSV1>
    <SONRS>
    <STATUS>
    <CODE>0</CODE>
    <SEVERITY>INFO</SEVERITY>
    </STATUS>
    <DTSERVER>20250325</DTSERVER>
    <LANGUAGE>POR</LANGUAGE>
    </SONRS>
    </SIGNONMSGSRSV1>
    <BANKMSGSRSV1>
    <STMTTRNRS>
    <TRNUID>1</TRNUID>
    <STATUS>
    <CODE>0</CODE>
    <SEVERITY>INFO</SEVERITY>
    </STATUS>
    <STMTRS>
    <CURDEF>BRL</CURDEF>
    <BANKACCTFROM>
    <BANKID>000</BANKID>
    <ACCTID>000</ACCTID>
    <ACCTTYPE>CHECKING</ACCTTYPE>
    </BANKACCTFROM>
    <BANKTRANLIST>
    """
        body = ""
        for i, row in df.iterrows():
            date = pd.to_datetime(row["Data"]).strftime("%Y%m%d")
            valor = row["Valor"]
            descricao = row["Descrição"]
            fitid = f"{i:06d}"
            trntype = "CREDIT" if valor > 0 else "DEBIT"
            body += f"""<STMTTRN>
    <TRNTYPE>{trntype}</TRNTYPE>
    <DTPOSTED>{date}</DTPOSTED>
    <TRNAMT>{valor}</TRNAMT>
    <FITID>{fitid}</FITID>
    <MEMO>{descricao}</MEMO>
    </STMTTRN>
    """
        footer = """</BANKTRANLIST>
    </STMTRS>
    </STMTTRNRS>
    </BANKMSGSRSV1>
    </OFX>"""
        return header + body + footer


    updated_ofx_content = generate_ofx_content(df_ofx_atualizado)
    # Botão de download para o arquivo OFX atualizado
    st.download_button(
        label="Baixar OFX Atualizado",
        data=updated_ofx_content,
        file_name="atualizado.ofx",
        mime="application/octet-stream"
    )