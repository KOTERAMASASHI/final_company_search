"""
このファイルは、画面表示以外の様々な関数定義のファイルです。
"""

############################################################
# ライブラリの読み込み
############################################################
import os
from dotenv import load_dotenv
import streamlit as st

from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import HumanMessage, AIMessage  # ✅ Cloud互換で統一
from langchain_openai import ChatOpenAI
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

import constants as ct


############################################################
# 設定関連
############################################################
load_dotenv()


############################################################
# 関数定義
############################################################

def get_source_icon(source: str):
    """
    メッセージと一緒に表示するアイコンの種類を取得
    """
    if source and str(source).startswith("http"):
        return ct.LINK_SOURCE_ICON
    return ct.DOC_SOURCE_ICON


def build_error_message(message: str) -> str:
    """
    エラーメッセージと管理者問い合わせテンプレートの連結
    """
    return "\n".join([message, ct.COMMON_ERROR_MESSAGE])


def _ensure_openai_key():
    """
    OPENAI_API_KEY が無い場合に、わかりやすい例外を投げる
    """
    if os.environ.get("OPENAI_API_KEY"):
        return

    try:
        if "OPENAI_API_KEY" in st.secrets:
            os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
            return
    except Exception:
        pass

    raise RuntimeError(
        "OPENAI_API_KEY が未設定です（Streamlit secrets または環境変数に設定してください）。"
    )


def _ensure_chat_history():
    """
    chat_history が無ければ初期化する
    """
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if st.session_state.chat_history is None:
        st.session_state.chat_history = []


def _append_history(user_text: str, assistant_text: str):
    """
    chat_history に BaseMessage を追加（HumanMessage / AIMessage）
    """
    _ensure_chat_history()
    st.session_state.chat_history.append(HumanMessage(content=user_text))
    st.session_state.chat_history.append(AIMessage(content=assistant_text))


def _normalize_llm_response(resp):
    """
    返り値の型ブレを吸収し、必ず
    {"answer": str, "context": list} を返す
    """
    if isinstance(resp, dict):
        answer = resp.get("answer")
        if answer is None:
            # 念のため別キーもフォールバック
            answer = resp.get("result") or resp.get("output_text") or ""
        context = resp.get("context") or []
        return {"answer": answer, "context": context, **resp}

    # AIMessage等
    if hasattr(resp, "content"):
        return {"answer": getattr(resp, "content") or "", "context": []}

    # str等
    return {"answer": str(resp), "context": []}


def get_llm_response(chat_message: str):
    """
    LLMからの回答取得（RAG + 会話履歴）
    """
    _ensure_openai_key()
    _ensure_chat_history()

    llm = ChatOpenAI(model=ct.MODEL, temperature=ct.TEMPERATURE)

    # 会話履歴があっても「単体で意味が通る質問文」に変換するプロンプト
    question_generator_template = ct.SYSTEM_PROMPT_CREATE_INDEPENDENT_TEXT
    question_generator_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", question_generator_template),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )

    # モードでプロンプト切替
    if st.session_state.mode == ct.ANSWER_MODE_1:
        question_answer_template = ct.SYSTEM_PROMPT_DOC_SEARCH
    else:
        question_answer_template = ct.SYSTEM_PROMPT_INQUIRY

    question_answer_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", question_answer_template),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )

    history_aware_retriever = create_history_aware_retriever(
        llm, st.session_state.retriever, question_generator_prompt
    )

    question_answer_chain = create_stuff_documents_chain(llm, question_answer_prompt)

    chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

    raw = chain.invoke({"input": chat_message, "chat_history": st.session_state.chat_history})
    llm_response = _normalize_llm_response(raw)

    answer_text = llm_response.get("answer", "") or ""
    _append_history(chat_message, answer_text)

    return llm_response