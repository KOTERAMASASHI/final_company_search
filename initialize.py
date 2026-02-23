"""
このファイルは、最初の画面読み込み時にのみ実行される初期化処理が記述されたファイルです。
"""

############################################################
# ライブラリの読み込み
############################################################
import os
import sys
import unicodedata
import logging
from logging.handlers import TimedRotatingFileHandler
from uuid import uuid4

from dotenv import load_dotenv
import streamlit as st

from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

import constants as ct


############################################################
# 設定関連
############################################################
# 「.env」ファイルで定義した環境変数の読み込み（ローカル用）
load_dotenv()

# Streamlit Cloud対策：Secretsがあれば環境変数へ反映
try:
    if "OPENAI_API_KEY" in st.secrets:
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
except Exception:
    pass


############################################################
# 関数定義
############################################################

def initialize():
    """
    画面読み込み時に実行する初期化処理
    """
    initialize_session_state()
    initialize_session_id()
    initialize_logger()
    initialize_retriever()


def initialize_logger():
    """
    ログ出力の設定
    """
    logger = logging.getLogger(ct.LOGGER_NAME)

    # すでに設定済みならスキップ（多重出力防止）
    if logger.hasHandlers():
        return

    # Cloud環境などで書き込み不可でもアプリを止めない
    try:
        os.makedirs(ct.LOG_DIR_PATH, exist_ok=True)

        log_handler = TimedRotatingFileHandler(
            os.path.join(ct.LOG_DIR_PATH, ct.LOG_FILE),
            when="D",
            encoding="utf8"
        )

        formatter = logging.Formatter(
            f"[%(levelname)s] %(asctime)s line %(lineno)s, in %(funcName)s, session_id={st.session_state.session_id}: %(message)s"
        )
        log_handler.setFormatter(formatter)

        logger.setLevel(logging.INFO)
        logger.addHandler(log_handler)

    except Exception:
        # ログ設定に失敗しても続行（提出/動作優先）
        return


def initialize_session_id():
    """
    セッションIDの作成
    """
    if "session_id" not in st.session_state:
        st.session_state.session_id = uuid4().hex


def initialize_retriever():
    """
    画面読み込み時にRAGのRetriever（ベクターストアから検索するオブジェクト）を作成
    """
    # すでにRetrieverが作成済みの場合、後続の処理を中断
    if "retriever" in st.session_state:
        return

    # RAGの参照先となるデータソースの読み込み
    docs_all = load_data_sources()

    # Windows対策（文字コード調整）
    for doc in docs_all:
        doc.page_content = adjust_string(doc.page_content)
        if getattr(doc, "metadata", None):
            for key in list(doc.metadata.keys()):
                doc.metadata[key] = adjust_string(doc.metadata[key])

    # 埋め込みモデル
    embeddings = OpenAIEmbeddings()

    # チャンク分割（課題②：定数化）
    text_splitter = CharacterTextSplitter(
        chunk_size=ct.CHUNK_SIZE,
        chunk_overlap=ct.CHUNK_OVERLAP,
        separator="\n"
    )

    splitted_docs = text_splitter.split_documents(docs_all)

    # ベクターストア作成
    db = Chroma.from_documents(splitted_docs, embedding=embeddings)

    # Retriever作成（課題①：3→5、課題②：定数化）
    st.session_state.retriever = db.as_retriever(
        search_kwargs={"k": ct.TOP_K}
    )


def initialize_session_state():
    """
    初期化データの用意
    """
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []


def load_data_sources():
    """
    RAGの参照先となるデータソースの読み込み

    Returns:
        読み込んだデータソース（Documentのリスト）
    """
    docs_all = []

    # フォルダ内ファイルを再帰的に読み込み（pdf/docx/csv/txtなど）
    recursive_file_check(ct.RAG_TOP_FOLDER_PATH, docs_all)

    # Webページ読み込み
    web_docs_all = []
    for web_url in ct.WEB_URL_LOAD_TARGETS:
        loader = WebBaseLoader(web_url)
        web_docs = loader.load()
        web_docs_all.extend(web_docs)

    docs_all.extend(web_docs_all)
    return docs_all


def recursive_file_check(path, docs_all):
    """
    データソースを再帰的に読み込み
    """
    if os.path.isdir(path):
        for file_name in os.listdir(path):
            full_path = os.path.join(path, file_name)
            recursive_file_check(full_path, docs_all)
    else:
        file_load(path, docs_all)


def file_load(path, docs_all):
    """
    ファイル内のデータ読み込み
    """
    file_extension = os.path.splitext(path)[1].lower()

    # 想定していたファイル形式の場合のみ読み込む（課題⑤：txtはconstants側で追加）
    if file_extension in ct.SUPPORTED_EXTENSIONS:
        loader_factory = ct.SUPPORTED_EXTENSIONS[file_extension]
        loader = loader_factory(path)
        docs = loader.load()
        docs_all.extend(docs)


def adjust_string(s):
    """
    Windows環境でRAGが正常動作するよう調整
    """
    if type(s) is not str:
        return s

    if sys.platform.startswith("win"):
        s = unicodedata.normalize("NFC", s)
        s = s.encode("cp932", "ignore").decode("cp932")
        return s

    return s