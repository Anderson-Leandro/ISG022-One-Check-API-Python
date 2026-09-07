from app.pdf_generator import SimplePdfCanvas, gerar_pdf_checklist


def test_simple_pdf_canvas_render():
    canvas = SimplePdfCanvas()
    canvas.add_text("Test Title", "Helvetica-Bold", 14, 50)
    canvas.draw_line(50, 700, 500, 700)
    canvas.draw_rect(50, 600, 100, 50, fill_color=(0.9, 0.9, 0.9), stroke_color=(0, 0, 0))
    canvas.new_page()
    canvas.add_text("Page 2", "Helvetica", 10, 50)

    pdf_bytes = canvas.render()
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"/Type /Catalog" in pdf_bytes
    assert b"/Helvetica" in pdf_bytes
    assert b"/Helvetica-Bold" in pdf_bytes
    assert pdf_bytes.endswith(b"%%EOF\n")


def test_gerar_pdf_checklist():
    checklist = {
        "id": "ck-123",
        "tipo": "inicial",
        "status": "aceito",
        "data_vistoria": "2026-03-01",
        "itens": [
            {
                "item_vistoria_id": "it-1",
                "comodo_id": "com-1",
                "estado": "bom",
                "observacao": "Tudo ok",
            }
        ],
    }
    contrato = {
        "id": "ct-123",
        "data_inicio": "2026-01-01",
        "data_fim": "2027-01-01",
        "status": "ativo",
    }
    imovel = {
        "tipo": "Apartamento",
        "tamanho": "60m²",
        "garagem_vagas": 1,
    }
    endereco = {
        "rua": "Rua das Flores",
        "numero": "123",
        "bairro": "Centro",
        "cidade": "Sao Paulo",
        "estado": "SP",
        "cep": "01001-000",
    }
    locatario = {"nome": "Joao Locatario", "email": "joao@teste.com"}
    vistoriador = {"nome": "Maria Vistoriadora", "email": "maria@teste.com"}
    aceite = {"status": "aceito", "created_at": "2026-03-02 10:00:00"}

    pdf_bytes = gerar_pdf_checklist(
        checklist=checklist,
        contrato=contrato,
        imovel=imovel,
        endereco=endereco,
        locatario=locatario,
        vistoriador=vistoriador,
        aceite=aceite,
    )

    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert len(pdf_bytes) > 200
