"""Regressões do pool real do psycopg2, com conexões inteiramente fictícias."""

from __future__ import annotations

import importlib.util
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import psycopg2
import pytest
from psycopg2 import extensions
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool


class FakeConnection:
    def __init__(self):
        self.closed = False
        self.cursor_factory = None
        self.info = SimpleNamespace(transaction_status=extensions.TRANSACTION_STATUS_IDLE)
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0
        self.exit_error = None
        self.rollback_error = None

    def commit(self):
        self.commits += 1
        self.info.transaction_status = extensions.TRANSACTION_STATUS_IDLE

    def rollback(self):
        self.rollbacks += 1
        if self.rollback_error:
            raise self.rollback_error
        self.info.transaction_status = extensions.TRANSACTION_STATUS_IDLE

    def close(self):
        self.closes += 1
        self.closed = True

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.exit_error:
            raise self.exit_error
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


@pytest.fixture
def subject(monkeypatch):
    # Carregar o módulo sem importar configurações reais nem ler arquivos .env.
    settings = ModuleType("config.settings")
    for key, value in {
        "PG_DB": "pool_unit_test",
        "PG_HOST": "localhost",
        "PG_PASS": "",
        "PG_PORT": 5432,
        "PG_USER": "pool_unit_test",
    }.items():
        setattr(settings, key, value)
    monkeypatch.setitem(sys.modules, "config.settings", settings)
    path = Path(__file__).resolve().parents[1] / "src" / "db_utils.py"
    spec = importlib.util.spec_from_file_location("_db_utils_pool_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    connections = []

    def connect(*args, **kwargs):
        conn = FakeConnection()
        connections.append(conn)
        return conn

    monkeypatch.setattr(psycopg2, "connect", connect)
    pool = ThreadedConnectionPool(2, 10)
    monkeypatch.setattr(module, "_pool", pool)
    yield SimpleNamespace(module=module, pool=pool, connections=connections)
    if not pool.closed:
        pool.closeall()


def test_usos_sequenciais_reutilizam_conexoes(subject):
    for _ in range(6):
        subject.module.get_connection().close()
    assert len(subject.connections) == 2
    assert len(subject.pool._pool) == 2
    assert not subject.pool._used
    assert not any(conn.closed for conn in subject.connections)


def test_contexto_confirma_transacao_e_devolve_conexao(subject):
    with subject.module.get_connection() as conn:
        physical = conn._conn
    assert physical.commits == 1
    assert physical.rollbacks == 0
    assert not physical.closed
    assert not subject.pool._used


def test_contexto_reverte_e_preserva_excecao_do_corpo(subject):
    error = ValueError("erro fictício no corpo")
    with pytest.raises(ValueError) as caught, subject.module.get_connection() as conn:
        physical = conn._conn
        raise error
    assert caught.value is error
    assert physical.rollbacks == 1
    assert physical.commits == 0
    assert not physical.closed
    assert not subject.pool._used


@pytest.mark.parametrize("body_error", [False, True])
def test_falha_ao_encerrar_transacao_descarta_conexao(subject, body_error):
    conn = subject.module.get_connection()
    physical = conn._conn
    error = psycopg2.OperationalError("falha fictícia ao encerrar transação")
    physical.exit_error = error
    with pytest.raises(psycopg2.OperationalError) as caught, conn:
        if body_error:
            raise ValueError("erro fictício no corpo")
    assert caught.value is error
    assert physical.closed
    assert physical not in subject.pool._pool
    assert not subject.pool._used
    conn.close()


def test_close_reverte_transacao_pendente_antes_da_reutilizacao(subject):
    conn = subject.module.get_connection()
    physical = conn._conn
    physical.info.transaction_status = extensions.TRANSACTION_STATUS_INTRANS
    conn.close()
    assert physical.rollbacks == 1
    assert physical.commits == 0
    assert not physical.closed
    assert subject.module.get_connection()._conn is physical


def test_falha_no_rollback_do_pool_descarta_e_preserva_erro(subject):
    conn = subject.module.get_connection()
    physical = conn._conn
    physical.info.transaction_status = extensions.TRANSACTION_STATUS_INERROR
    error = psycopg2.OperationalError("rollback fictício falhou")
    physical.rollback_error = error
    with pytest.raises(psycopg2.OperationalError) as caught:
        conn.close()
    assert caught.value is error
    assert physical.closed
    assert not subject.pool._used
    conn.close()


@pytest.mark.parametrize("closed", [False, True])
def test_conexao_quebrada_nao_volta_ao_pool(subject, closed):
    conn = subject.module.get_connection()
    physical = conn._conn
    if closed:
        physical.close()
    else:
        physical.info.transaction_status = extensions.TRANSACTION_STATUS_UNKNOWN
    conn.close()
    assert physical.closed
    assert physical not in subject.pool._pool
    assert not subject.pool._used


def test_close_duplicado_devolve_uma_unica_vez(subject, monkeypatch):
    putconn = Mock(wraps=subject.pool.putconn)
    monkeypatch.setattr(subject.pool, "putconn", putconn)
    conn = subject.module.get_connection()
    conn.close()
    conn.close()
    assert putconn.call_count == 1


def test_close_concorrente_devolve_uma_unica_vez(subject, monkeypatch):
    started, finish = Event(), Event()
    original = subject.pool.putconn

    def putconn(*args, **kwargs):
        started.set()
        assert finish.wait(timeout=5)
        return original(*args, **kwargs)

    spy = Mock(side_effect=putconn)
    monkeypatch.setattr(subject.pool, "putconn", spy)
    conn = subject.module.get_connection()
    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(conn.close) for _ in range(8)]
            try:
                assert started.wait(timeout=5)
            finally:
                finish.set()
            for future in futures:
                future.result(timeout=5)
    finally:
        finish.set()
    assert spy.call_count == 1
    assert not subject.pool._used


def test_aquisicoes_concorrentes_recebem_conexoes_distintas(subject):
    barrier = Barrier(8)

    def acquire():
        with subject.module.get_connection() as conn:
            barrier.wait(timeout=5)
            return id(conn._conn)

    with ThreadPoolExecutor(max_workers=8) as executor:
        ids = list(executor.map(lambda _: acquire(), range(8)))
    assert len(set(ids)) == 8
    assert len(subject.connections) == 8
    assert not subject.pool._used


def test_close_concorrente_aguarda_o_fim_da_transacao(subject, monkeypatch):
    started, finish, returned = Event(), Event(), Event()
    conn = subject.module.get_connection()
    physical = conn._conn
    original = FakeConnection.__exit__

    def exit_transaction(self, *args):
        started.set()
        assert finish.wait(timeout=5)
        return original(self, *args)

    monkeypatch.setattr(FakeConnection, "__exit__", exit_transaction)
    original_putconn = subject.pool.putconn

    def putconn(*args, **kwargs):
        assert physical.commits == 1
        returned.set()
        return original_putconn(*args, **kwargs)

    spy = Mock(side_effect=putconn)
    monkeypatch.setattr(subject.pool, "putconn", spy)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            exiting = executor.submit(conn.__exit__, None, None, None)
            try:
                assert started.wait(timeout=5)
                closing = executor.submit(conn.close)
                assert not returned.is_set()
            finally:
                finish.set()
            exiting.result(timeout=5)
            closing.result(timeout=5)
    finally:
        finish.set()
    assert returned.is_set()
    assert spy.call_count == 1


@pytest.mark.parametrize("operation", ["commit", "cursor_factory", "attribute", "enter"])
def test_wrapper_devolvido_nao_acessa_conexao_reutilizada(subject, operation):
    conn = subject.module.get_connection()
    physical = conn._conn
    conn.close()
    next_conn = subject.module.get_connection()
    assert next_conn._conn is physical
    with pytest.raises(psycopg2.InterfaceError):
        if operation == "commit":
            conn.commit()
        elif operation == "cursor_factory":
            conn.cursor_factory = RealDictCursor
        elif operation == "attribute":
            _ = conn.cursor_factory
        else:
            conn.__enter__()
    assert physical.commits == 0
    assert physical.cursor_factory is extensions.cursor
    next_conn.close()


def test_close_no_corpo_nao_confirma_transacao_do_proximo_usuario(subject):
    with subject.module.get_connection() as conn:
        physical = conn._conn
        conn.close()
        next_conn = subject.module.get_connection()
        assert next_conn._conn is physical
    assert physical.commits == 0
    assert subject.pool._used
    next_conn.close()


def test_cursor_padrao_nao_herda_realdict_do_usuario_anterior(subject):
    conn = subject.module.get_real_dict_connection()
    physical = conn._conn
    assert conn.cursor_factory is RealDictCursor
    conn.close()
    with subject.module.get_connection() as next_conn:
        assert next_conn._conn is physical
        assert next_conn.cursor_factory is extensions.cursor


def test_erro_de_limpeza_nao_mascara_erro_da_transacao(subject, monkeypatch, caplog):
    conn = subject.module.get_connection()
    error = psycopg2.OperationalError("erro fictício da transação")
    conn._conn.exit_error = error
    monkeypatch.setattr(subject.pool, "putconn", Mock(side_effect=RuntimeError("erro do pool")))
    with pytest.raises(psycopg2.OperationalError) as caught, conn:
        pass
    assert caught.value is error
    assert "Falha ao descartar conexão" in caplog.text
