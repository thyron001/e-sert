"""Ritmo en vivo (2026-11-18): el visor cambia la velocidad en plena corrida."""

from types import SimpleNamespace

from traci.correr_guiado import PublicadorSnapshots, Ritmo


def test_fijar_cambia_el_factor_y_reinicia_la_referencia():
    r = Ritmo(2.0)
    r.on_paso(None, 10.0)
    assert r._inicio is not None
    r.fijar(10.0)
    assert r.factor == 10.0 and r._inicio is None
    r.fijar(10.0)  # mismo factor: no cambia nada
    r.on_paso(None, 11.0)
    assert r._inicio[1] == 11.0
    r.fijar(0)     # inválido: se ignora
    assert r.factor == 10.0


def test_si_no_da_abasto_no_recupera_el_atraso_a_toda_velocidad(monkeypatch):
    import traci.correr_guiado as cg

    reloj = {"t": 100.0}
    monkeypatch.setattr(cg.time, "perf_counter", lambda: reloj["t"])
    r = Ritmo(1.0)
    r.on_paso(None, 0.0)
    reloj["t"] += 30.0      # pasaron 30 s reales y la simulación solo avanzó 5 s: va atrasada
    r.on_paso(None, 5.0)
    assert r._inicio == (130.0, 5.0)  # nueva referencia: no corre a toda velocidad para alcanzar


def test_el_publicador_aplica_el_ritmo_de_la_respuesta():
    pub = SimpleNamespace(al_responder=None)
    snap = PublicadorSnapshots(pub, None, None, None, SimpleNamespace(activos={}), None)
    snap.ritmo = Ritmo(2.0)
    pub.al_responder({"espejos": [], "ordenes": [], "ritmo": 5})
    assert snap.ritmo.factor == 5.0
    pub.al_responder({"espejos": [], "ordenes": [], "ritmo": None})
    assert snap.ritmo.factor == 5.0
