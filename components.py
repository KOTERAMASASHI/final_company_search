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
# 内部関数
############################################################
def _format_source_with_page(doc) -> str:
    """
    Documentのmetadataから参照元表示文字列を作る。
    PDFのみページ番号を付ける。（課題④）
    """
    meta = getattr(doc, "metadata", {}) or {}
    src = meta.get("source") or meta.get("file_path") or meta.get("path") or ""
    if not src:
        return ""

    ext = os.path.splitext(str(src))[1].lower()
    if ext == ".pdf":
        page = meta.get("page")
        if page is None:
            page = meta.get("page_number")

        # PyMuPDFLoaderは0始まりが多いので +1 して人間向けにする
        if isinstance(page, int):
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
    会話ログの一覧表示
    """
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):

            if message["role"] == "user":
                st.markdown(message["content"])
                continue

            # assistant
            content = message["content"]

            # 旧データ互換（assistantのcontentが文字列の場合）
            if isinstance(content, str):
                st.markdown(content)
                continue

            mode = content.get("mode")

            # ==========================================
            # 社内文書検索
            # ==========================================
            if mode == ct.ANSWER_MODE_1:
                if "no_file_path_flg" not in content:
                    st.markdown(content.get("main_message", ""))

                    main_file_path = content.get("main_file_path", "")
                    if main_file_path:
                        icon = utils.get_source_icon(main_file_path)
                        st.success(main_file_path, icon=icon)

                    if "sub_message" in content:
                        st.markdown(content.get("sub_message", ""))

                        for sub_choice in content.get("sub_choices", []):
                            src = sub_choice.get("source", "")
                            if not src:
                                continue
                            icon = utils.get_source_icon(src)
                            st.info(src, icon=icon)
                else:
                    st.markdown(content.get("answer", ""))

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
    answer_text = llm_response.get("answer", "")

    # constants側が無くても落ちないようにフォールバック
    no_doc_answer = getattr(ct, "NO_DOC_MATCH_ANSWER", "該当する資料は見つかりませんでした。")

    if context_docs and answer_text != no_doc_answer:
        # メイン表示：最初のDocumentを採用（ただしPDFならページ込み）
        main_display = _format_source_with_page(context_docs[0])

        main_message = "入力内容に関する情報は、以下のファイルに含まれている可能性があります。"
        st.markdown(main_message)

        if main_display:
            icon = utils.get_source_icon(main_display)
            st.success(main_display, icon=icon)

        # サブ候補：重複排除（PDFページ込みでユニーク化）
        sub_candidates = []
        for doc in context_docs[1:]:
            s = _format_source_with_page(doc)
            if s:
                sub_candidates.append(s)

        # メインと同じ表示を除外
        sub_candidates = [s for s in sub_candidates if s != main_display]
        sub_candidates = _unique_in_order(sub_candidates)

        sub_choices = [{"source": s} for s in sub_candidates]

        if sub_choices:
            sub_message = "その他、ファイルありかの候補を提示します。"
            st.markdown(sub_message)
            for sub_choice in sub_choices:
                icon = utils.get_source_icon(sub_choice["source"])
                st.info(sub_choice["source"], icon=icon)

        content = {
            "mode": ct.ANSWER_MODE_1,
            "main_message": main_message,
            "main_file_path": main_display,
        }
        if sub_choices:
            content["sub_message"] = sub_message
            content["sub_choices"] = sub_choices

        return content

    # 関連ドキュメントなし
    no_doc_message = getattr(
        ct,
        "NO_DOC_MATCH_MESSAGE",
        "入力内容と関連する社内文書が見つかりませんでした。\n入力内容を変更してください。"
    )
    st.markdown(no_doc_message)

    return {
        "mode": ct.ANSWER_MODE_1,
        "answer": no_doc_message,
        "no_file_path_flg": True,
    }


def display_inquiry_llm_response(llm_response):
    """
    「社内問い合わせ」モードにおけるLLMレスポンスを表示し、
    画面表示用の辞書を返す
    """
    context_docs = llm_response.get("context") or []
    answer_text = llm_response.get("answer", "")

    final_answer = answer_text if answer_text else getattr(ct, "INQUIRY_NO_MATCH_ANSWER", "回答に必要な情報が見つかりませんでした。")
    st.markdown(final_answer)

    # 参照元のファイルパスを（PDFはページ番号込みで）重複排除
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

    if sources:
        content["message"] = "情報源"
        content["file_info_list"] = sources

        st.divider()
        st.markdown("##### 情報源")
        for s in sources:
            icon = utils.get_source_icon(s)
            st.info(s, icon=icon)

    return content