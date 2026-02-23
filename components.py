"""
このファイルは、画面表示に特化した関数定義のファイルです。
"""

############################################################
# ライブラリの読み込み
############################################################
import os
import streamlit as st
import utils
import constants as ct


############################################################
# 内部ユーティリティ
############################################################

def _get_answer_text(llm_response: dict) -> str:
    """
    LangChainの戻り値が answer / output_text のどちらでも落ちないよう吸収
    """
    if not isinstance(llm_response, dict):
        return ""
    return (llm_response.get("answer") or llm_response.get("output_text") or "")


def _format_source_with_page(doc) -> str:
    """
    PDFのみページ番号を付与（問題④）
    """
    meta = getattr(doc, "metadata", {}) or {}
    src = meta.get("source") or ""
    if not src:
        return ""

    ext = os.path.splitext(str(src))[1].lower()
    if ext == ".pdf":
        page = meta.get("page")
        if isinstance(page, int):
            # PyMuPDFLoaderは0始まりのことが多いので +1
            return f"{src}（p.{page + 1}）"

    return str(src)


def _unique_in_order(items):
    seen = set()
    out = []
    for x in items:
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _normalize_sub_choices(sub_choices):
    """
    sub_choices が list[dict] / list[str] どちらでも表示できるようにする
    """
    out = []
    if not sub_choices:
        return out

    for item in sub_choices:
        if isinstance(item, dict):
            s = item.get("source", "")
        else:
            s = str(item)
        if s:
            out.append({"source": s})
    return out


############################################################
# 関数定義
############################################################

def display_app_title():
    """
    タイトル表示
    """
    st.markdown(f"## {ct.APP_NAME}")


def display_select_mode():
    """
    回答モードのラジオボタンを表示
    """
    col1, col2 = st.columns([100, 1])
    with col1:
        st.session_state.mode = st.radio(
            label="",
            options=[ct.ANSWER_MODE_1, ct.ANSWER_MODE_2],
            label_visibility="collapsed",
        )


def display_initial_ai_message():
    """
    AIメッセージの初期表示
    """
    with st.chat_message("assistant"):
        st.markdown(
            "こんにちは。私は社内文書の情報をもとに回答する生成AIチャットボットです。"
            "上記で利用目的を選択し、画面下部のチャット欄からメッセージを送信してください。"
        )

        st.markdown("**【「社内文書検索」を選択した場合】**")
        st.info("入力内容と関連性が高い社内文書のありかを検索できます。")
        st.code("【入力例】\n社員の育成方針に関するMTGの議事録", wrap_lines=True, language=None)

        st.markdown("**【「社内問い合わせ」を選択した場合】**")
        st.info("質問・要望に対して、社内文書の情報をもとに回答を得られます。")
        st.code("【入力例】\n人事部に所属している従業員情報を一覧化して", wrap_lines=True, language=None)


def display_conversation_log():
    """
    会話ログの一覧表示（どんな形の過去ログでも落ちないよう堅牢化）
    """
    for message in st.session_state.messages:
        role = message.get("role", "")
        content = message.get("content", "")

        with st.chat_message(role if role else "assistant"):

            # user
            if role == "user":
                st.markdown(content if isinstance(content, str) else str(content))
                continue

            # assistant（旧データ互換：contentが文字列のケース）
            if isinstance(content, str):
                st.markdown(content)
                continue

            if not isinstance(content, dict):
                st.markdown(str(content))
                continue

            mode = content.get("mode")

            # ==========================================
            # 社内文書検索
            # ==========================================
            if mode == ct.ANSWER_MODE_1:
                # no_doc
                if content.get("no_file_path_flg"):
                    st.markdown(content.get("answer", ""))
                    continue

                st.markdown(content.get("main_message", ""))

                main_file_path = content.get("main_file_path", "")
                if main_file_path:
                    icon = utils.get_source_icon(main_file_path)
                    st.success(main_file_path, icon=icon)

                sub_message = content.get("sub_message")
                sub_choices = _normalize_sub_choices(content.get("sub_choices"))

                if sub_message and sub_choices:
                    st.markdown(sub_message)
                    for sub in sub_choices:
                        src = sub.get("source", "")
                        if not src:
                            continue
                        icon = utils.get_source_icon(src)
                        st.info(src, icon=icon)

            # ==========================================
            # 社内問い合わせ
            # ==========================================
            else:
                st.markdown(content.get("answer", ""))

                file_info_list = content.get("file_info_list")
                if file_info_list:
                    st.divider()
                    st.markdown(f"##### {content.get('message', '情報源')}")
                    for file_info in file_info_list:
                        icon = utils.get_source_icon(file_info)
                        st.info(file_info, icon=icon)


def display_search_llm_response(llm_response):
    """
    「社内文書検索」モードにおけるLLMレスポンスを表示し、
    画面表示用の辞書を返す
    """
    context_docs = llm_response.get("context") or []
    answer_text = _get_answer_text(llm_response)

    no_doc_answer = getattr(ct, "NO_DOC_MATCH_ANSWER", "該当資料なし")
    no_doc_message = getattr(
        ct,
        "NO_DOC_MATCH_MESSAGE",
        "入力内容と関連する社内文書が見つかりませんでした。\n入力内容を変更してください。"
    )

    # 返答が「該当資料なし」or 文脈が空 → 該当なし表示
    if (not context_docs) or (answer_text == no_doc_answer):
        st.markdown(no_doc_message)
        return {
            "mode": ct.ANSWER_MODE_1,
            "answer": no_doc_message,
            "no_file_path_flg": True,
        }

    # 該当あり：上位1件＋候補
    main_display = _format_source_with_page(context_docs[0])

    main_message = "入力内容に関する情報は、以下のファイルに含まれている可能性があります。"
    st.markdown(main_message)

    if main_display:
        icon = utils.get_source_icon(main_display)
        st.success(main_display, icon=icon)

    sub_candidates = []
    for doc in context_docs[1:]:
        s = _format_source_with_page(doc)
        if s and s != main_display:
            sub_candidates.append(s)
    sub_candidates = _unique_in_order(sub_candidates)

    content = {
        "mode": ct.ANSWER_MODE_1,
        "main_message": main_message,
        "main_file_path": main_display,
    }

    if sub_candidates:
        sub_message = "その他、ファイルありかの候補を提示します。"
        st.markdown(sub_message)
        for s in sub_candidates:
            icon = utils.get_source_icon(s)
            st.info(s, icon=icon)

        # 既存ロジック互換：list[dict]で保持
        content["sub_message"] = sub_message
        content["sub_choices"] = [{"source": s} for s in sub_candidates]

    return content


def display_contact_llm_response(llm_response):
    """
    「社内問い合わせ」モードにおけるLLMレスポンスを表示し、
    画面表示用の辞書を返す（落ちない完全安定版）
    """
    context_docs = llm_response.get("context") or []
    answer_text = _get_answer_text(llm_response)

    # 「該当なし」用の定数があれば使う
    no_match = getattr(ct, "INQUIRY_NO_MATCH_ANSWER", "回答に必要な情報が見つかりませんでした。")
    final_answer = answer_text if answer_text else no_match

    st.markdown(final_answer)

    # 情報源（PDFだけページ付き）
    sources = []
    for doc in context_docs:
        s = _format_source_with_page(doc)
        if s:
            sources.append(s)
    sources = _unique_in_order(sources)

    content = {
        "mode": ct.ANSWER_MODE_2,
        "answer": final_answer,
    }

    # 情報源があるときだけ付与（ここが “該当なし時に落ちる” の対策の肝）
    if sources:
        st.divider()
        st.markdown("##### 情報源")
        for s in sources:
            icon = utils.get_source_icon(s)
            st.info(s, icon=icon)

        content["message"] = "情報源"
        content["file_info_list"] = sources

    return content