#!/usr/bin/env python3
"""
apply_template.py
-----------------
Aplica um template Word (.dotx ou .docx) a um ou mais documentos, copiando:
  - Todos os estilos (parágrafo, caractere, tabela, lista)
  - As configurações de página (margens, tamanho, orientação)
  - A capa (primeira seção / página de capa), se presente no template

Dependências:
    pip install python-docx lxml

Uso:
    # Arquivo único
    python apply_template.py template.dotx documento.docx --output saida.docx

    # Pasta inteira
    python apply_template.py template.dotx ./meus_docs --output ./docs_formatados

    # Forçar inclusão da capa do template mesmo que o doc já tenha uma
    python apply_template.py template.dotx ./meus_docs --output ./out --cover
"""

import argparse
import copy
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

try:
    from docx import Document
    from docx.oxml.ns import qn
    from lxml import etree
except ImportError:
    sys.exit(
        "Dependências não encontradas. Execute:\n"
        "    pip install python-docx lxml"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_child(parent, tag):
    """Retorna o primeiro filho com determinada tag, ou None."""
    return parent.find(qn(tag)) if parent is not None else None


def _remove_all(parent, tag):
    """Remove todos os filhos com determinada tag."""
    for child in parent.findall(qn(tag)):
        parent.remove(child)


def _copy_styles(template_doc, target_doc):
    """
    Copia todos os estilos do template para o documento alvo.
    Estilos com o mesmo styleId são substituídos; novos são adicionados.
    """
    tmpl_styles_elem = template_doc.styles.element
    tgt_styles_elem = target_doc.styles.element

    # Mapeia styleId -> elemento no destino para lookup rápido
    existing = {
        s.get(qn("w:styleId")): s
        for s in tgt_styles_elem.findall(qn("w:style"))
    }

    for style_elem in tmpl_styles_elem.findall(qn("w:style")):
        style_id = style_elem.get(qn("w:styleId"))
        new_elem = copy.deepcopy(style_elem)

        if style_id in existing:
            tgt_styles_elem.remove(existing[style_id])

        tgt_styles_elem.append(new_elem)

    # Copia docDefaults (fontes e espaçamentos padrão)
    tmpl_defaults = _first_child(tmpl_styles_elem, "w:docDefaults")
    if tmpl_defaults is not None:
        tgt_defaults = _first_child(tgt_styles_elem, "w:docDefaults")
        if tgt_defaults is not None:
            tgt_styles_elem.remove(tgt_defaults)
        tgt_styles_elem.insert(0, copy.deepcopy(tmpl_defaults))


def _copy_page_layout(src_sectPr, dst_sectPr):
    """Copia dimensões de página, margens e orientação entre sectPr."""
    for tag in ("w:pgSz", "w:pgMar", "w:cols", "w:docGrid"):
        src_el = src_sectPr.find(qn(tag))
        if src_el is not None:
            _remove_all(dst_sectPr, tag)
            dst_sectPr.append(copy.deepcopy(src_el))


def _is_cover_section(section_body_elements):
    """
    Heurística simples: considera capa a seção que começa com uma quebra
    de página específica (w:lastRenderedPageBreak / sectPr com tipo coverPage
    ou firstPage) ou que usa o estilo 'Cover'/'Capa'.
    """
    cover_style_names = {"cover", "capa", "título", "title page"}
    for el in section_body_elements:
        # Verifica estilo do parágrafo
        pStyle = el.find(".//" + qn("w:pStyle"))
        if pStyle is not None:
            val = (pStyle.get(qn("w:val")) or "").lower()
            if any(c in val for c in cover_style_names):
                return True
    return False


def _get_cover_elements(template_doc):
    """
    Retorna os elementos XML da capa do template (até a primeira sectPr interna
    ou primeira quebra de página de seção).
    Retorna lista vazia se não houver capa identificável.
    """
    body = template_doc.element.body
    all_children = list(body)

    # Procura o primeiro sectPr interno (seção de capa)
    cover_elems = []
    for child in all_children:
        # sectPr no último parágrafo marca fim de seção
        inner_sectPr = child.find(".//" + qn("w:sectPr"))
        if inner_sectPr is not None:
            cover_elems.append(child)
            # Verifica se é realmente uma capa pela heurística
            if _is_cover_section(cover_elems) or _has_cover_type(inner_sectPr):
                return cover_elems
            # Se não parece capa, retorna vazio
            return []
        cover_elems.append(child)

    # Não achou sectPr interna — template tem apenas uma seção, sem capa
    return []


def _has_cover_type(sectPr):
    """Verifica se sectPr possui titlePg ou tipo 'firstPage'."""
    title_pg = sectPr.find(qn("w:titlePg"))
    pg_type = sectPr.find(qn("w:type"))
    if title_pg is not None:
        return True
    if pg_type is not None:
        val = pg_type.get(qn("w:val"), "")
        return val in ("firstPage",)
    return False


def _insert_cover(target_doc, cover_elements):
    """
    Insere os elementos de capa no início do corpo do documento alvo.
    Se o documento já começar com uma seção interna (outra capa), substitui.
    """
    body = target_doc.element.body
    existing = list(body)

    # Remove capa existente (até o primeiro sectPr interno)
    insert_pos = 0
    for i, child in enumerate(existing):
        inner_sectPr = child.find(".//" + qn("w:sectPr"))
        if inner_sectPr is not None:
            # Remove do início até aqui (inclusive)
            for j in range(i + 1):
                body.remove(existing[j])
            insert_pos = 0
            break

    # Insere capa do template no início
    for idx, elem in enumerate(cover_elements):
        body.insert(insert_pos + idx, copy.deepcopy(elem))


def _copy_theme(template_doc, target_doc):
    """Copia o tema (cores, fontes) do template para o documento alvo."""
    try:
        tmpl_part = template_doc.part
        tgt_part = target_doc.part

        # Acessa a relação de tema
        for rel in tmpl_part.rels.values():
            if "theme" in rel.reltype.lower():
                theme_part = rel.target_part
                # Tenta replicar no destino
                for tgt_rel in list(tgt_part.rels.values()):
                    if "theme" in tgt_rel.reltype.lower():
                        tgt_rel.target_part._blob = theme_part._blob
                        break
                break
    except Exception:
        pass  # Tema é opcional; falha silenciosa


# ---------------------------------------------------------------------------
# Função principal de aplicação
# ---------------------------------------------------------------------------

def _open_as_docx(path: Path) -> "Document":
    """
    Abre qualquer arquivo Word (incluindo .dotx) como um Document do python-docx.
    Arquivos .dotx têm content-type diferente de .docx; copiá-los para um
    arquivo temporário com extensão .docx contorna a rejeição do python-docx.
    """
    if path.suffix.lower() in (".dotx", ".dot"):
        tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
        try:
            shutil.copy2(str(path), tmp.name)
            tmp.close()
            return Document(tmp.name)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
    return Document(str(path))


def apply_template(template_path: Path, input_path: Path, output_path: Path,
                   force_cover: bool = True):
    """
    Aplica o template a input_path e salva em output_path.

    Parâmetros
    ----------
    template_path : Path  – arquivo .dotx / .docx do template
    input_path    : Path  – documento .docx de entrada
    output_path   : Path  – arquivo .docx de saída
    force_cover   : bool  – True = copia capa do template mesmo se doc já tiver
    """
    template_doc = _open_as_docx(template_path)
    target_doc = _open_as_docx(input_path)

    # 1. Copia estilos
    _copy_styles(template_doc, target_doc)

    # 2. Copia tema
    _copy_theme(template_doc, target_doc)

    # 3. Copia layout de página da seção principal
    tmpl_body = template_doc.element.body
    tgt_body = target_doc.element.body

    tmpl_sectPr = tmpl_body.find(qn("w:sectPr"))
    tgt_sectPr = tgt_body.find(qn("w:sectPr"))
    if tmpl_sectPr is not None and tgt_sectPr is not None:
        _copy_page_layout(tmpl_sectPr, tgt_sectPr)

    # 4. Copia capa, se existir no template
    cover_elements = _get_cover_elements(template_doc)
    if cover_elements:
        if force_cover:
            _insert_cover(target_doc, cover_elements)
            print(f"  ✔ Capa inserida")
        else:
            # Só insere se o documento alvo não tiver capa
            target_cover = _get_cover_elements(target_doc)
            if not target_cover:
                _insert_cover(target_doc, cover_elements)
                print(f"  ✔ Capa inserida (documento não tinha capa)")
            else:
                print(f"  ℹ Documento já possui capa — mantida (use --cover para substituir)")
    else:
        print(f"  ℹ Template não possui capa identificável")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    target_doc.save(str(output_path))
    print(f"  ✔ Salvo em: {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Aplica template .dotx a documentos Word (.docx).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "template",
        help="Caminho para o arquivo template (.dotx ou .docx)",
    )
    parser.add_argument(
        "input",
        help="Documento .docx de entrada ou pasta com vários documentos",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help=(
            "Arquivo .docx de saída (quando input é arquivo) ou "
            "pasta de saída (quando input é pasta). "
            "Padrão: sobrescreve o arquivo / cria pasta '<input>_formatado'."
        ),
    )
    parser.add_argument(
        "--cover",
        action="store_true",
        default=True,
        help="Substitui a capa do documento pela capa do template (padrão: ativo)",
    )
    parser.add_argument(
        "--no-cover",
        action="store_false",
        dest="cover",
        help="Não substitui a capa se o documento já tiver uma",
    )

    args = parser.parse_args()

    template_path = Path(args.template)
    if not template_path.exists():
        sys.exit(f"Template não encontrado: {template_path}")

    input_path = Path(args.input)

    # --- Modo pasta ---
    if input_path.is_dir():
        docs = list(input_path.rglob("*.docx"))
        if not docs:
            sys.exit(f"Nenhum arquivo .docx encontrado em: {input_path}")

        output_dir = Path(args.output) if args.output else input_path.parent / (input_path.name + "_formatado")
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"Template : {template_path}")
        print(f"Entrada  : {input_path}  ({len(docs)} arquivo(s))")
        print(f"Saída    : {output_dir}\n")

        for doc_path in docs:
            rel = doc_path.relative_to(input_path)
            out_file = output_dir / rel
            print(f"→ {doc_path.name}")
            try:
                apply_template(template_path, doc_path, out_file, force_cover=args.cover)
            except Exception as exc:
                print(f"  ✖ Erro: {exc}")
                traceback.print_exc()

    # --- Modo arquivo único ---
    elif input_path.is_file():
        if args.output:
            output_file = Path(args.output)
        else:
            output_file = input_path.parent / (input_path.stem + "_formatado.docx")

        print(f"Template : {template_path}")
        print(f"Entrada  : {input_path}")
        print(f"Saída    : {output_file}\n")

        print(f"→ {input_path.name}")
        try:
            apply_template(template_path, input_path, output_file, force_cover=args.cover)
        except Exception as exc:
            print(f"  ✖ Erro: {exc}")
            traceback.print_exc()
            sys.exit(1)

    else:
        sys.exit(f"Entrada não encontrada: {input_path}")


if __name__ == "__main__":
    main()
