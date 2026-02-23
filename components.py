import os
import streamlit as st
import utils
import constants as ct


def _get_answer_text(resp):
    if not isinstance(resp, dict):
        return ""
    return resp.get("answer") or resp.get("output_text") or ""


def _format_source(doc):
    meta = getattr(doc, "metadata", {}) or {}
    src = meta.get("source")
    if not src:
        return None

    ext = os.path.splitext(src)[1].lower()
    if ext == ".pdf":
        page = meta.get("page")
        if isinstance(page, int):
            return f"{src}（p.{page + 1}）"

    return src


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
        st.markdown("こんにちは。私は社内文書の情報をもとに回答する生成AIチャットボットです。")


def display_conversation_log():
    for msg in st.session_state.messages:

        role = msg.get("role")
        content = msg.get("content")

        with st.chat_message(role):

            if role == "user":
                st.markdown(content)
                continue

            # assistant

            if isinstance(content, str):
                st.markdown(content)
                continue

            if not isinstance(content, dict):
                st.markdown(str(content))
                continue

            mode = content.get("mode")

            if mode == ct.ANSWER_MODE_1:

                if content.get("no_file_path_flg"):
                    st.markdown(content.get("answer", ""))
                    continue

                st.markdown(content.get("main_message", ""))

                main = content.get("main_file_path")
                if main:
                    st.success(main)

                for sub in content.get("sub_choices", []):
                    if isinstance(sub, dict):
                        st.info(sub.get("source"))
                    else:
                        st.info(sub)

            else:
                st.markdown(content.get("answer", ""))

                files = content.get("file_info_list")
                if files:
                    st.divider()
                    st.markdown("##### 情報源")
                    for f in files:
                        st.info(f)


def display_search_llm_response(llm_response):

    context = llm_response.get("context", [])
    answer = _get_answer_text(llm_response)

    if not context or answer == ct.NO_DOC_MATCH_ANSWER:
        st.markdown(ct.NO_DOC_MATCH_MESSAGE)
        return {
            "mode": ct.ANSWER_MODE_1,
            "answer": ct.NO_DOC_MATCH_MESSAGE,
            "no_file_path_flg": True
        }

    main = _format_source(context[0])

    st.markdown("入力内容に関する情報は、以下のファイルに含まれている可能性があります。")
    st.success(main)

    subs = []
    for doc in context[1:]:
        s = _format_source(doc)
        if s and s != main:
            subs.append({"source": s})

    if subs:
        st.markdown("その他、ファイルありかの候補を提示します。")
        for s in subs:
            st.info(s["source"])

    return {
        "mode": ct.ANSWER_MODE_1,
        "main_message": "入力内容に関する情報は、以下のファイルに含まれている可能性があります。",
        "main_file_path": main,
        "sub_choices": subs
    }


def display_contact_llm_response(llm_response):

    answer = _get_answer_text(llm_response)
    st.markdown(answer)

    context = llm_response.get("context", [])

    sources = []
    for doc in context:
        s = _format_source(doc)
        if s and s not in sources:
            sources.append(s)

    if sources:
        st.divider()
        st.markdown("##### 情報源")
        for s in sources:
            st.info(s)

    return {
        "mode": ct.ANSWER_MODE_2,
        "answer": answer,
        "file_info_list": sources if sources else []
    }