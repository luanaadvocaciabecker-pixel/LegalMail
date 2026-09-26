import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from legalmail_prazos import cli
from legalmail_prazos.legalmail_client import ItemEntrada


def test_verificar_processo_caso_recorrente(tmp_path: Path, planilha_sintetica: Path, capsys):
    prazos_nums = tmp_path / "prazos_nums.json"
    prazos_nums.write_text("[]", encoding="utf-8")

    codigo = cli.main(
        [
            "verificar-processo",
            "5000000-00.2025.8.24.0038",
            "--prazos-nums-json",
            str(prazos_nums),
            "--planilha",
            str(planilha_sintetica),
        ]
    )

    saida = capsys.readouterr().out
    assert codigo == 0
    assert "CASO RECORRENTE" in saida


def test_verificar_processo_caso_novo(tmp_path: Path, capsys):
    prazos_nums = tmp_path / "prazos_nums.json"
    prazos_nums.write_text("[]", encoding="utf-8")

    codigo = cli.main(
        [
            "verificar-processo",
            "9999999-99.2099.8.24.0038",
            "--prazos-nums-json",
            str(prazos_nums),
        ]
    )

    saida = capsys.readouterr().out
    assert codigo == 0
    assert "CASO NOVO" in saida


def test_calcular_prazo_sem_tribunal(capsys):
    codigo = cli.main(
        [
            "calcular-prazo",
            "2026-08-24",
            "15",
            "--regime",
            "civel_dias_uteis",
        ]
    )

    saida = capsys.readouterr().out
    assert codigo == 0
    assert "data final legal (fatal): 2026-09-16" in saida


def test_calcular_prazo_com_tribunal_confirmado(capsys):
    codigo = cli.main(
        [
            "calcular-prazo",
            "2026-08-24",
            "15",
            "--regime",
            "civel_dias_uteis",
            "--tribunal",
            "TJSC 1G",
        ]
    )

    saida = capsys.readouterr().out
    assert codigo == 0
    assert "aviso" not in saida


def test_calcular_prazo_com_tribunal_nao_confirmado_avisa(capsys):
    codigo = cli.main(
        [
            "calcular-prazo",
            "2026-08-24",
            "15",
            "--regime",
            "civel_dias_uteis",
            "--tribunal",
            "STJ",
        ]
    )

    saida = capsys.readouterr().out
    assert codigo == 0
    assert "aviso" in saida
    assert "STJ" in saida


@dataclass
class FakeClienteEncarregamento:
    usuario_id_por_nome: dict[str, int] = field(default_factory=dict)
    itens_entrada: list = field(default_factory=list)
    encarregados: list = field(default_factory=list)
    arquivados: list = field(default_factory=list)

    def listar_entrada(self):
        return self.itens_entrada

    def localizar_usuario_por_nome(self, nome: str):
        return self.usuario_id_por_nome.get(nome)

    def encarregar_advogado(self, id_legalmail_processo: str, id_usuario: int) -> None:
        self.encarregados.append((id_legalmail_processo, id_usuario))

    def arquivar_para_acervo(self, id_legalmail_processo: str) -> None:
        self.arquivados.append(id_legalmail_processo)


def test_encarregar_entrada_usa_cliente_e_mapa(
    monkeypatch, tmp_path: Path, planilha_sintetica: Path, capsys
):
    cliente_fake = FakeClienteEncarregamento(
        usuario_id_por_nome={"FULANA COMPLETA": 7},
        itens_entrada=[
            ItemEntrada(
                id_legalmail="item-1",
                numero_processo="5000000-00.2025.8.24.0038",
                tribunal="TJSC 1G",
                cliente_x_parte="CLIENTE TESTE",
                conteudo_intimacao="teor qualquer",
                data_disponibilizacao=date(2026, 8, 24),
            )
        ],
    )
    monkeypatch.setattr(cli, "cliente_a_partir_do_ambiente", lambda: cliente_fake)

    mapa_path = tmp_path / "mapa.json"
    mapa_path.write_text(json.dumps({"Fulana": "FULANA COMPLETA"}), encoding="utf-8")

    codigo = cli.main(
        [
            "encarregar-entrada",
            "--planilha",
            str(planilha_sintetica),
            "--mapa-advogados",
            str(mapa_path),
        ]
    )

    saida = capsys.readouterr().out
    assert codigo == 0
    assert cliente_fake.encarregados == [("item-1", 7)]
    assert cliente_fake.arquivados == ["item-1"]
    assert "encarregados" in saida
