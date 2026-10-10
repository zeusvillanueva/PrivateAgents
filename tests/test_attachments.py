from shared.attachments import parse_attachments


def test_parse_and_strip():
    text, a = parse_attachments('<attachments>{"vector_store_ids":["vs_1"],"file_ids":["file-2"]}</attachments>\nhello')
    assert text == "hello" and a.vector_store_ids == ["vs_1"] and a.file_ids == ["file-2"]


def test_rejects_bad_ids_and_json():
    _, a = parse_attachments('<attachments>{"file_ids":["x; rm","ok_1"]}</attachments><attachments>{bad</attachments>')
    assert a.file_ids == ["ok_1"]


def test_no_block():
    assert parse_attachments("hi")[0] == "hi"
