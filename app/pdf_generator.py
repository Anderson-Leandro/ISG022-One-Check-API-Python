"""
Gerador de laudos de vistoria em formato PDF (OneCheck).
Produz documentos PDF 1.4 válidos e leves sem dependências externas.
"""
from datetime import datetime


class SimplePdfCanvas:
    def __init__(self, page_width: float = 595.28, page_height: float = 841.89):
        # Dimensões padrão A4 em points
        self.width = page_width
        self.height = page_height
        self.pages: list[list[str]] = [[]]
        self.current_page = 0
        self.y = self.height - 50

    def new_page(self):
        self.pages.append([])
        self.current_page += 1
        self.y = self.height - 50

    def check_page_break(self, needed_height: float):
        if self.y - needed_height < 50:
            self.new_page()

    def add_text(self, text: str, font: str = "Helvetica", size: float = 10, x: float = 50, color=(0, 0, 0)):
        r, g, b = color
        stream = self.pages[self.current_page]
        escaped = (
            text.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
            .encode("latin-1", "replace")
            .decode("latin-1")
        )
        stream.append(f"{r:.2f} {g:.2f} {b:.2f} rg")
        stream.append(f"BT /{font} {size} Tf {x:.2f} {self.y:.2f} Td ({escaped}) Tj ET")

    def draw_line(self, x1: float, y1: float, x2: float, y2: float, width: float = 1, color=(0.7, 0.7, 0.7)):
        r, g, b = color
        stream = self.pages[self.current_page]
        stream.append(f"{r:.2f} {g:.2f} {b:.2f} RG {width:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def draw_rect(self, x: float, y: float, w: float, h: float, fill_color=None, stroke_color=None):
        stream = self.pages[self.current_page]
        if fill_color:
            r, g, b = fill_color
            stream.append(f"{r:.2f} {g:.2f} {b:.2f} rg")
        if stroke_color:
            r, g, b = stroke_color
            stream.append(f"{r:.2f} {g:.2f} {b:.2f} RG")

        op = "B" if (fill_color and stroke_color) else ("f" if fill_color else "S")
        stream.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re {op}")

    def render(self) -> bytes:
        objects: list[bytes] = []

        # 1: Catalog
        objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")

        # 3: Helvetica Font
        font_helvetica = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
        # 4: Helvetica-Bold Font
        font_bold = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"

        num_pages = len(self.pages)
        page_obj_ids = [5 + i * 2 for i in range(num_pages)]
        content_obj_ids = [6 + i * 2 for i in range(num_pages)]

        kids_str = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
        pages_obj = f"<< /Type /Pages /Kids [{kids_str}] /Count {num_pages} >>".encode("ascii")

        all_objs = [b"", objects[0], pages_obj, font_helvetica, font_bold]

        for i in range(num_pages):
            content_data = "\n".join(self.pages[i]).encode("latin-1")
            page_obj = (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.width} {self.height}] "
                f"/Resources << /Font << /Helvetica 3 0 R /Helvetica-Bold 4 0 R >> >> "
                f"/Contents {content_obj_ids[i]} 0 R >>"
            ).encode("ascii")
            content_obj = f"<< /Length {len(content_data)} >>\nstream\n".encode("ascii") + content_data + b"\nendstream"
            all_objs.append(page_obj)
            all_objs.append(content_obj)

        pdf_bytes = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]

        for i in range(1, len(all_objs)):
            offsets.append(len(pdf_bytes))
            pdf_bytes.extend(f"{i} 0 obj\n".encode("ascii"))
            pdf_bytes.extend(all_objs[i])
            pdf_bytes.extend(b"\nendobj\n")

        xref_offset = len(pdf_bytes)
        pdf_bytes.extend(f"xref\n0 {len(all_objs)}\n0000000000 65535 f \n".encode("ascii"))
        for i in range(1, len(all_objs)):
            pdf_bytes.extend(f"{offsets[i]:010d} 00000 n \n".encode("ascii"))

        pdf_bytes.extend(
            f"trailer\n<< /Size {len(all_objs)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
        )
        return bytes(pdf_bytes)


def gerar_pdf_checklist(
    checklist: dict,
    contrato: dict,
    imovel: dict,
    endereco: dict | None,
    locatario: dict,
    vistoriador: dict,
    aceite: dict | None,
) -> bytes:
    canvas = SimplePdfCanvas()

    # Header
    canvas.draw_rect(40, canvas.y - 10, 515, 35, fill_color=(0.1, 0.15, 0.3))
    canvas.y -= 2
    canvas.add_text("ONECHECK - LAUDO DE VISTORIA IMOBILIARIA", "Helvetica-Bold", 14, 50, color=(1, 1, 1))
    canvas.y -= 14
    canvas.add_text(f"Emissao: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", "Helvetica", 9, 50, color=(0.85, 0.85, 0.85))
    canvas.y -= 30

    # Imóvel
    canvas.draw_rect(40, canvas.y - 2, 515, 18, fill_color=(0.93, 0.94, 0.96))
    canvas.add_text("1. DADOS DO IMOVEL", "Helvetica-Bold", 10, 50, color=(0.1, 0.15, 0.3))
    canvas.y -= 16

    end_str = "Nao informado"
    if endereco:
        end_str = f"{endereco.get('rua', '')}, {endereco.get('numero', '') or 'S/N'} - {endereco.get('bairro', '')} - {endereco.get('cidade', '')}/{endereco.get('estado', '')} (CEP: {endereco.get('cep', '')})"

    canvas.add_text(f"Tipo: {imovel.get('tipo', 'N/A')}  |  Tamanho: {imovel.get('tamanho', 'N/A')}  |  Garagem: {imovel.get('garagem_vagas', 0)} vaga(s)", "Helvetica", 9, 50)
    canvas.y -= 12
    canvas.add_text(f"Endereco: {end_str}", "Helvetica", 9, 50)
    canvas.y -= 20

    # Contrato e Partes
    canvas.draw_rect(40, canvas.y - 2, 515, 18, fill_color=(0.93, 0.94, 0.96))
    canvas.add_text("2. DADOS DO CONTRATO E PARTES", "Helvetica-Bold", 10, 50, color=(0.1, 0.15, 0.3))
    canvas.y -= 16
    canvas.add_text(f"Contrato ID: {contrato.get('id', 'N/A')}  |  Status: {contrato.get('status', 'N/A')}", "Helvetica", 9, 50)
    canvas.y -= 12
    canvas.add_text(f"Periodo: {contrato.get('data_inicio', '')} ate {contrato.get('data_fim', '')}", "Helvetica", 9, 50)
    canvas.y -= 12
    canvas.add_text(f"Locatario: {locatario.get('nome', 'N/A')} ({locatario.get('email', 'N/A')})", "Helvetica", 9, 50)
    canvas.y -= 12
    canvas.add_text(f"Vistoriador: {vistoriador.get('nome', 'N/A')} ({vistoriador.get('email', 'N/A')})", "Helvetica", 9, 50)
    canvas.y -= 20

    # Vistoria
    canvas.draw_rect(40, canvas.y - 2, 515, 18, fill_color=(0.93, 0.94, 0.96))
    tipo_str = "Inicial" if checklist.get("tipo") == "inicial" else "Encerramento"
    canvas.add_text(f"3. DADOS DA VISTORIA ({tipo_str.upper()})", "Helvetica-Bold", 10, 50, color=(0.1, 0.15, 0.3))
    canvas.y -= 16
    canvas.add_text(f"Checklist ID: {checklist.get('id', 'N/A')}  |  Status: {checklist.get('status', 'N/A')}  |  Data: {checklist.get('data_vistoria', 'N/A')}", "Helvetica", 9, 50)
    canvas.y -= 20

    # Itens
    canvas.draw_rect(40, canvas.y - 2, 515, 18, fill_color=(0.93, 0.94, 0.96))
    canvas.add_text("4. ITENS VISTORIADOS E ESTADO DE CONSERVACAO", "Helvetica-Bold", 10, 50, color=(0.1, 0.15, 0.3))
    canvas.y -= 16

    itens = checklist.get("itens", [])
    if not itens:
        canvas.add_text("Nenhum item registrado nesta vistoria.", "Helvetica", 9, 50, color=(0.5, 0.5, 0.5))
        canvas.y -= 15
    else:
        for idx, item in enumerate(itens, 1):
            canvas.check_page_break(35)
            estado = (item.get("estado") or "N/A").upper()
            obs = item.get("observacao") or "Sem observacoes"
            canvas.add_text(f"{idx}. Item ID: {item.get('item_vistoria_id', 'N/A')}  |  Comodo: {item.get('comodo_id', 'N/A')}", "Helvetica-Bold", 9, 50)
            canvas.y -= 11
            canvas.add_text(f"   Estado: {estado}  |  Observacao: {obs}", "Helvetica", 9, 50)
            canvas.y -= 14

    canvas.y -= 10
    canvas.check_page_break(50)

    # Termo de Aceite / Assinatura
    canvas.draw_rect(40, canvas.y - 2, 515, 18, fill_color=(0.93, 0.94, 0.96))
    canvas.add_text("5. TERMO DE ACEITE E ASSINATURA DIGITAL", "Helvetica-Bold", 10, 50, color=(0.1, 0.15, 0.3))
    canvas.y -= 16

    if aceite:
        status_ac = (aceite.get("status") or "N/A").upper()
        dt_ac = aceite.get("created_at") or "N/A"
        motivo = f" | Motivo: {aceite.get('motivo_rejeicao')}" if aceite.get("motivo_rejeicao") else ""
        canvas.add_text(f"Status do Aceite: {status_ac} em {dt_ac}{motivo}", "Helvetica-Bold", 9, 50)
        canvas.y -= 12
        canvas.add_text(f"Assinado digitalmente por: {locatario.get('nome', 'N/A')} (Locatario Titular)", "Helvetica", 9, 50)
    else:
        canvas.add_text("Status do Aceite: PENDENTE DE ASSINATURA PELO LOCATARIO", "Helvetica", 9, 50, color=(0.6, 0.3, 0.1))

    canvas.y -= 25
    canvas.draw_line(50, canvas.y, 545, canvas.y, width=0.5, color=(0.8, 0.8, 0.8))
    canvas.y -= 12
    canvas.add_text("Documento gerado eletronicamente pela Plataforma OneCheck. Autenticidade garantida por chave digital e logs de auditoria.", "Helvetica", 7, 50, color=(0.5, 0.5, 0.5))

    return canvas.render()
