"""
このファイルは、画面表示に特化した関数定義のファイルです。
"""

import os
import streamlit as st
import utils
import constants as ct


# ==================================================
# 共通ユーティリティ
# ==================================================

def _format_source(doc):
    meta = getattr(doc, "metadata", {}) or {}
    src = meta.get("source", "")
    if not src:
        return ""

    ext = os.path.splitext(src)[1].lower()

    # PDFのみページ番号表示（問題④）
    if ext == ".pdf":
        page = meta.get("page")
        if isinstance(page, int):
            return f"{src}（p.{page + 1}）"

    return src


def _unique_list(lst):
    seen = set()
    result = []
    for x in lst:
        if x and x not in seen:
            seen.add(x)
            result.append(x)
    return result


# ==================================================
# 画面表示系
# ==================================================

def display_app_title():
    st.markdown(f"## {ct.APP_NAME}")


def display_select_mode():
    col1, col2 = st.columns([100, 1])
    with col1:
        st.session_state.mode = st.radio(
            label="",
            options=[ct.ANSWER_MODE_1, ct.ANSWER_MODE_2],
            label_visibility="collapsed"
        )


def display_initial_ai_message():
    with st.chat_message("assistant"):
        st.markdown(
            "こんにちは。私は社内文書の情報をもとに回答する生成AIチャットボットです。"
            "上記で利用目的を選択し、画面下部のチャット欄からメッセージを送信してください。"
        )


def display_conversation_log():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):

            if message["role"] == "user":
                st.markdown(message["content"])
                continue

            content = message["content"]

            if isinstance(content, str):
                st.markdown(content)
                continue

            mode = content.get("mode")

            # 文書検索モード
            if mode == ct.ANSWER_MODE_1:

                if not content.get("no_file_path_flg"):

                    st.markdown(content.get("main_message", ""))

                    main_file = content.get("main_file_path", "")
                    if main_file:
                        icon = utils.get_source_icon(main_file)
                        st.success(main_file, icon=icon)

                    if content.get("sub_choices"):
                        st.markdown(content.get("sub_message", ""))
                        for sub in content["sub_choices"]:
                            icon = utils.get_source_icon(sub)
                            st.info(sub, icon=icon)

                else:
                    st.markdown(content.get("answer", ""))

            # 問い合わせモード
            else:
                st.markdown(content.get("answer", ""))

                if content.get("file_info_list"):
                    st.divider()
                    st.markdown("##### 情報源")
                    for file_info in content["file_info_list"]:
                        icon = utils.get_source_icon(file_info)
                        st.info(file_info, icon=icon)


# ==================================================
# 文書検索モード表示
# ==================================================

def display_search_llm_response(llm_response):

    context_docs = llm_response.get("context", [])
    answer_text = llm_response.get("answer") or llm_response.get("output_text") or ""

    if context_docs and answer_text != ct.NO_DOC_MATCH_ANSWER:

        main_display = _format_source(context_docs[0])

        st.markdown("入力内容に関する情報は、以下のファイルに含まれている可能性があります。")

        icon = utils.get_source_icon(main_display)
        st.success(main_display, icon=icon)

        sub_list = []
        for doc in context_docs[1:]:
            s = _format_source(doc)
            if s != main_display:
                sub_list.append(s)

        sub_list = _unique_list(sub_list)

        if sub_list:
            st.markdown("その他、ファイルありかの候補を提示します。")
            for s in sub_list:
                icon = utils.get_source_icon(s)
                st.info(s, icon=icon)

        return {
            "mode": ct.ANSWER_MODE_1,
            "main_message": "入力内容に関する情報は、以下のファイルに含まれている可能性があります。",
            "main_file_path": main_display,
            "sub_message": "その他、ファイルありかの候補を提示します。",
            "sub_choices": sub_list
        }

    else:
        st.markdown(ct.NO_DOC_MATCH_MESSAGE)
        return {
            "mode": ct.ANSWER_MODE_1,
            "answer": ct.NO_DOC_MATCH_MESSAGE,
            "no_file_path_flg": True
        }


# ==================================================
# 問い合わせモード表示（完全安定版）
# ==================================================

def display_contact_llm_response(llm_response):

    # answerキー安全取得
    answer = llm_response.get("answer") or llm_response.get("output_text") or ""

    st.markdown(answer)

    sources = []
    for doc in llm_response.get("context", []):
        s = _format_source(doc)
        if s:
            sources.append(s)

    sources = _unique_list(sources)

    if sources:
        st.divider()
        st.markdown("##### 情報源")
        for s in sources:
            icon = utils.get_source_icon(s)
            st.info(s, icon=icon)

    return {
        "mode": ct.ANSWER_MODE_2,
        "answer": answer,
        "file_info_list": sources
    }