// Vista 3D del visor (2026-11-18), con three.js.
//
// Lo más simple posible: los edificios de OpenStreetMap extruidos (2 a 4 pisos), las calles de
// SUMO, los puestos SERT en líneas punteadas (verde con plazas libres, rojo lleno), los autos
// estacionados en sus plazas y los autos en movimiento como volúmenes con el color de su estado.
// Los autos de la app llevan el nombre de su usuario encima. No hay fondo satelital.
//
// No tiene estado propio de la simulación: lee la `CapaCalle` del mapa 2D (puestos, vehículos,
// peatones), que `principal.js` sigue alimentando con cada snapshot. Así el 2D y el 3D muestran
// siempre lo mismo y se puede cambiar de vista en cualquier momento.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";

const M_POR_GRADO = 111320;
const ALTURA_CAMARA_INICIAL = 520;
const MAX_ESTACIONADOS = 7000;
const MAX_MOVIMIENTO = 2500;
const MAX_PEATONES = 400;
const COLOR = {
  cielo: 0xcfe0ee, suelo: 0xd9ddd3, calle: 0x8d949d, verde: 0x9fcb8f,
  libre: new THREE.Color("#22a559"), lleno: new THREE.Color("#e04848"), peaton: 0x2563eb, propio: 0xffd60a,
};

/** Cinta plana de ancho `ancho` a lo largo de `puntos` ([x, z]), a la altura `y`. */
function cinta(puntos, ancho, y) {
  const pos = [], idx = [];
  for (let i = 0; i < puntos.length; i++) {
    const a = puntos[Math.max(i - 1, 0)], b = puntos[Math.min(i + 1, puntos.length - 1)];
    let dx = b[0] - a[0], dz = b[1] - a[1];
    const l = Math.hypot(dx, dz) || 1;
    dx /= l; dz /= l;
    const [x, z] = puntos[i];
    pos.push(x - dz * ancho / 2, y, z + dx * ancho / 2, x + dz * ancho / 2, y, z - dx * ancho / 2);
    if (i) { const k = 2 * i; idx.push(k - 2, k - 1, k, k - 1, k + 1, k); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  return g;
}

/** Trozos de `puntos` de `trazo` metros separados por `hueco` metros (línea punteada). */
function punteada(puntos, trazo, hueco) {
  const trozos = [];
  let actual = [puntos[0]], dentro = true, resto = trazo;
  for (let i = 1; i < puntos.length; i++) {
    let [x0, z0] = puntos[i - 1];
    const [x1, z1] = puntos[i];
    let l = Math.hypot(x1 - x0, z1 - z0);
    while (l > 1e-6) {
      const paso = Math.min(resto, l), k = paso / l;
      x0 += (x1 - x0) * k; z0 += (z1 - z0) * k; l -= paso; resto -= paso;
      if (dentro) actual.push([x0, z0]);
      if (resto <= 1e-6) {
        if (dentro && actual.length > 1) trozos.push(actual);
        dentro = !dentro; resto = dentro ? trazo : hueco; actual = [[x0, z0]];
      }
    }
  }
  if (dentro && actual.length > 1) trozos.push(actual);
  return trozos;
}

function geometriaAuto() {
  const cuerpo = new THREE.BoxGeometry(1.8, 0.8, 4.4); cuerpo.translate(0, 0.55, 0);
  const cabina = new THREE.BoxGeometry(1.55, 0.6, 2.2); cabina.translate(0, 1.25, 0.25);
  return mergeGeometries([cuerpo, cabina]);
}

function geometriaPeaton() {
  const cuerpo = new THREE.CylinderGeometry(0.45, 0.45, 1.4, 10); cuerpo.translate(0, 0.7, 0);
  const cabeza = new THREE.SphereGeometry(0.38, 12, 8); cabeza.translate(0, 1.75, 0);
  return mergeGeometries([cuerpo, cabeza]);
}

const angulo = (a, b, k) => { let d = b - a; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI; return a + d * k; };

export class Vista3D {
  /** `contenedor`: el div de la vista; `calle`: la `CapaCalle` del mapa 2D; `datos`: escena3d.json. */
  constructor(contenedor, calle, { datos = "./datos/escena3d.json" } = {}) {
    this.el = contenedor;
    this.calle = calle;
    this.activa = true;
    this.origen = [-2.8974, -79.0045];
    this.cos0 = Math.cos(this.origen[0] * Math.PI / 180);
    this.moviles = new Map();     // id → {x, z, r, de:{x,z,r}, a:{x,z,r}, t0, color, halo, etiqueta}
    this.ultimoSnapshot = 0;
    this.intervalo = 1000;
    this.puestosListos = false;
    this.rangos = new Map();      // puesto → [inicio, fin] en los colores de la cinta punteada
    this.etiquetas = new Map();   // id → div con el nombre del usuario de la app
    this.siguiendo = null;
    this._montar();
    fetch(datos).then((r) => r.json()).then((d) => this._escena(d)).catch((e) => console.warn("Escena 3D:", e));
    this._enganchar();
    this._bucle = this._bucle.bind(this);
    requestAnimationFrame(this._bucle);
  }

  local(lat, lon) {
    return [(lon - this.origen[1]) * M_POR_GRADO * this.cos0, -(lat - this.origen[0]) * M_POR_GRADO];
  }

  mostrar(si) { this.activa = si; this.el.hidden = !si; if (si) this._tamano(); }

  // ------------------------------------------------------------------ montaje

  _montar() {
    const r = this.renderer = new THREE.WebGLRenderer({ antialias: true });
    r.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    this.el.appendChild(r.domElement);
    const s = this.scene = new THREE.Scene();
    s.background = new THREE.Color(COLOR.cielo);
    s.fog = new THREE.Fog(COLOR.cielo, 1400, 3200);
    this.camara = new THREE.PerspectiveCamera(45, 1, 2, 6000);
    this.camara.position.set(-260, ALTURA_CAMARA_INICIAL, 420);
    const c = this.controles = new OrbitControls(this.camara, r.domElement);
    c.target.set(0, 0, 0);
    c.enableDamping = true;
    c.maxPolarAngle = 1.38;
    c.minDistance = 25; c.maxDistance = 2600;
    c.screenSpacePanning = false;
    c.addEventListener("start", () => { this.siguiendo = null; });
    s.add(new THREE.HemisphereLight(0xffffff, 0x8a9099, 1.1));
    const sol = new THREE.DirectionalLight(0xffffff, 1.4);
    sol.position.set(-300, 600, 200);
    s.add(sol);
    const suelo = new THREE.Mesh(new THREE.PlaneGeometry(8000, 8000), new THREE.MeshLambertMaterial({ color: COLOR.suelo }));
    suelo.rotation.x = -Math.PI / 2;
    s.add(suelo);
    // autos y peatones (instanciados)
    const auto = geometriaAuto();
    const mat = () => new THREE.MeshLambertMaterial({ color: 0xffffff });
    this.estacionados = new THREE.InstancedMesh(auto, mat(), MAX_ESTACIONADOS);
    this.movimiento = new THREE.InstancedMesh(auto, mat(), MAX_MOVIMIENTO);
    this.peatones = new THREE.InstancedMesh(geometriaPeaton(), new THREE.MeshLambertMaterial({ color: COLOR.peaton }), MAX_PEATONES);
    for (const m of [this.estacionados, this.movimiento, this.peatones]) { m.count = 0; m.frustumCulled = false; s.add(m); }
    this.estacionados.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_ESTACIONADOS * 3), 3);
    this.movimiento.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_MOVIMIENTO * 3), 3);
    // autos de la app: más grandes, amarillos y con un anillo
    this.anillos = new THREE.Group();
    s.add(this.anillos);
    this.geoAnillo = new THREE.RingGeometry(6, 7.5, 40); this.geoAnillo.rotateX(-Math.PI / 2);
    this.matAnillo = new THREE.MeshBasicMaterial({ color: COLOR.propio, transparent: true, opacity: 0.85, side: THREE.DoubleSide });
    this.capaTexto = document.createElement("div");
    this.capaTexto.className = "rotulos3d";
    this.el.appendChild(this.capaTexto);
    const credito = document.createElement("div");
    credito.className = "credito3d";
    credito.textContent = "Edificios y calles © OpenStreetMap (red de SUMO) · three.js · arrastra para girar, rueda para acercar";
    this.el.appendChild(credito);
    new ResizeObserver(() => this._tamano()).observe(this.el);
    this._tamano();
  }

  _escena(d) {
    this.origen = d.origen;
    this.cos0 = Math.cos(this.origen[0] * Math.PI / 180);
    const edificios = [];
    // fachadas del Centro Histórico: blancos, cremas y ocres claros
    const tonos = ["#f4efe6", "#efe2c8", "#e9d3b4", "#f2e8d8", "#e6cfc0", "#ece6dc"].map((c) => new THREE.Color(c));
    d.edificios.forEach((e, i) => {
      const forma = new THREE.Shape(e.p.map(([x, y]) => new THREE.Vector2(x, y)));
      const g = new THREE.ExtrudeGeometry(forma, { depth: e.h, bevelEnabled: false });
      g.rotateX(-Math.PI / 2);
      g.deleteAttribute("uv");
      const c = tonos[i % tonos.length], n = g.attributes.position.count, col = new Float32Array(n * 3);
      for (let k = 0; k < n; k++) { col[3 * k] = c.r; col[3 * k + 1] = c.g; col[3 * k + 2] = c.b; }
      g.setAttribute("color", new THREE.BufferAttribute(col, 3));
      edificios.push(g);
    });
    if (edificios.length) {
      const m = new THREE.Mesh(mergeGeometries(edificios), new THREE.MeshLambertMaterial({ vertexColors: true }));
      this.scene.add(m);
    }
    const verdes = d.verdes.map((p) => {
      const g = new THREE.ShapeGeometry(new THREE.Shape(p.map(([x, y]) => new THREE.Vector2(x, y))));
      g.rotateX(-Math.PI / 2); g.translate(0, 0.03, 0); g.deleteAttribute("uv");
      return g;
    });
    if (verdes.length) this.scene.add(new THREE.Mesh(mergeGeometries(verdes), new THREE.MeshLambertMaterial({ color: COLOR.verde })));
    const calles = d.calles.map((c) => cinta(c.p.map(([x, y]) => [x, -y]), c.w, 0.06));
    if (calles.length) this.scene.add(new THREE.Mesh(mergeGeometries(calles), new THREE.MeshBasicMaterial({ color: COLOR.calle, side: THREE.DoubleSide })));
    this._puestos();
  }

  _tamano() {
    const w = this.el.clientWidth, h = this.el.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h);
    this.camara.aspect = w / h;
    this.camara.updateProjectionMatrix();
  }

  // ------------------------------------------------------------------ datos de la CapaCalle

  _enganchar() {
    const c = this.calle;
    const veh = c.fijarVehiculos.bind(c), ocu = c.fijarOcupacion.bind(c);
    c.fijarVehiculos = (lista) => { veh(lista); this._vehiculos(); };
    c.fijarOcupacion = (lista) => { ocu(lista); this._puestos(); this._estacionados(); };
  }

  _puestos() {
    if (this.puestosListos || !this.calle.puestos.size || !this.scene) return;
    const geos = [];
    let n = 0;
    for (const p of this.calle.puestos.values()) {
      const inicio = n;
      for (const tramo of punteada(p.linea.map(([la, lo]) => this.local(la, lo)), 3, 2)) {
        const g = cinta(tramo, 1.1, 0.15);
        n += g.attributes.position.count;
        geos.push(g);
      }
      this.rangos.set(p.id, [inicio, n]);
    }
    if (!geos.length) return;
    const g = mergeGeometries(geos);
    g.setAttribute("color", new THREE.Float32BufferAttribute(new Float32Array(n * 3), 3));
    this.cintaPuestos = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide }));
    this.scene.add(this.cintaPuestos);
    this.puestosListos = true;
  }

  _estacionados() {
    if (!this.puestosListos) return;
    const col = this.cintaPuestos.geometry.attributes.color;
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), uno = new THREE.Vector3(1, 1, 1);
    const gris = new THREE.Color("#c3cbd6");
    let k = 0;
    for (const p of this.calle.puestos.values()) {
      const [a, b] = this.rangos.get(p.id) || [0, 0];
      const c = p.ocupados >= p.capacidad ? COLOR.lleno : COLOR.libre;
      for (let i = a; i < b; i++) col.setXYZ(i, c.r, c.g, c.b);
      for (let i = 0; i < p.ocupados && i < p.plazas.length && k < MAX_ESTACIONADOS; i++, k++) {
        const [la, lo, r] = p.plazas[i];
        const [x, z] = this.local(la, lo);
        q.setFromEuler(e.set(0, -r * Math.PI / 180, 0));
        this.estacionados.setMatrixAt(k, m.compose(new THREE.Vector3(x, 0, z), q, uno));
        this.estacionados.setColorAt(k, gris);
      }
    }
    col.needsUpdate = true;
    this.estacionados.count = k;
    this.estacionados.instanceMatrix.needsUpdate = true;
    if (this.estacionados.instanceColor) this.estacionados.instanceColor.needsUpdate = true;
  }

  _vehiculos() {
    const ahora = performance.now();
    if (this.ultimoSnapshot) this.intervalo = Math.min(Math.max(ahora - this.ultimoSnapshot, 100), 1500);
    this.ultimoSnapshot = ahora;
    const vistos = new Set();
    for (const v of this.calle.vehiculos.values()) {
      vistos.add(v.id);
      const [x, z] = this.local(v.lat, v.lon);
      let m = this.moviles.get(v.id);
      if (!m) { m = { x, z, r: v.rumbo }; this.moviles.set(v.id, m); }
      m.de = { x: m.x, z: m.z, r: m.r };
      m.a = { x, z, r: v.rumbo };
      m.t0 = ahora;
      m.color = v.color; m.halo = v.halo; m.etiqueta = v.etiqueta;
    }
    for (const id of [...this.moviles.keys()]) if (!vistos.has(id)) this.moviles.delete(id);
  }

  // ------------------------------------------------------------------ dibujo

  _bucle() {
    requestAnimationFrame(this._bucle);
    if (!this.activa) return;
    const ahora = performance.now();
    const mtx = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), color = new THREE.Color();
    const uno = new THREE.Vector3(1.4, 1.4, 1.4), grande = new THREE.Vector3(2.4, 2.4, 2.4);
    let k = 0, anillo = 0;
    const halos = [];
    for (const [id, m] of this.moviles) {
      const f = Math.min((ahora - m.t0) / this.intervalo, 1);
      m.x = m.de.x + (m.a.x - m.de.x) * f;
      m.z = m.de.z + (m.a.z - m.de.z) * f;
      m.r = angulo(m.de.r, m.a.r, f);
      if (k >= MAX_MOVIMIENTO) continue;
      q.setFromEuler(e.set(0, -m.r, 0));
      this.movimiento.setMatrixAt(k, mtx.compose(new THREE.Vector3(m.x, 0, m.z), q, m.halo ? grande : uno));
      this.movimiento.setColorAt(k, color.set(m.halo ? COLOR.propio : m.color || "#e5e7eb"));
      k++;
      if (m.halo) halos.push([id, m]);
    }
    this.movimiento.count = k;
    this.movimiento.instanceMatrix.needsUpdate = true;
    if (this.movimiento.instanceColor) this.movimiento.instanceColor.needsUpdate = true;
    // anillos pulsantes bajo los autos de la app
    const pulso = 1 + 0.25 * Math.sin(ahora / 260);
    while (this.anillos.children.length < halos.length) this.anillos.add(new THREE.Mesh(this.geoAnillo, this.matAnillo));
    this.anillos.children.forEach((a, i) => {
      a.visible = i < halos.length;
      if (a.visible) { a.position.set(halos[i][1].x, 0.2, halos[i][1].z); a.scale.setScalar(pulso); }
    });
    // peatones de la app
    let p = 0;
    for (const ped of this.calle.peatones) {
      if (p >= MAX_PEATONES) break;
      const [x, z] = this.local(ped.lat, ped.lon);
      this.peatones.setMatrixAt(p++, mtx.compose(new THREE.Vector3(x, 0, z), q.identity(), grande));
    }
    this.peatones.count = p;
    this.peatones.instanceMatrix.needsUpdate = true;
    // cámara que sigue a un auto de la app
    if (this.siguiendo) {
      const m = this.moviles.get(this.siguiendo);
      if (m) {
        const d = new THREE.Vector3(m.x, 0, m.z).sub(this.controles.target);
        this.controles.target.add(d); this.camara.position.add(d);
      } else this.siguiendo = null;
    }
    this.controles.update();
    this.renderer.render(this.scene, this.camara);
    this._rotulos(halos);
  }

  /** Nombres de los usuarios de la app (siempre) y de las calles (de cerca), en HTML sobre el lienzo. */
  _rotulos(halos) {
    const w = this.el.clientWidth, h = this.el.clientHeight, v = new THREE.Vector3();
    const vivos = new Set();
    for (const [id, m] of halos) {
      if (!m.etiqueta) continue;
      vivos.add(id);
      let div = this.etiquetas.get(id);
      if (!div) {
        div = document.createElement("button");
        div.type = "button";
        div.className = "rotulo-usuario";
        div.title = "Seguir este auto con la cámara";
        div.onclick = () => { this.siguiendo = this.siguiendo === id ? null : id; };
        this.capaTexto.appendChild(div);
        this.etiquetas.set(id, div);
      }
      div.textContent = (this.siguiendo === id ? "◉ " : "") + m.etiqueta;
      v.set(m.x, 9, m.z).project(this.camara);
      div.hidden = v.z > 1;
      div.style.transform = `translate(-50%,-100%) translate(${(v.x + 1) / 2 * w}px,${(1 - v.y) / 2 * h}px)`;
    }
    for (const [id, div] of this.etiquetas) if (!vivos.has(id)) { div.remove(); this.etiquetas.delete(id); }
    // calles: solo con la cámara cerca, para no llenar la vista
    const cerca = this.camara.position.distanceTo(this.controles.target) < 650;
    if (!this.divCalles) {
      this.divCalles = (this.calle.rotulos || []).map(([nombre, la1, lo1, la2, lo2]) => {
        const div = document.createElement("div");
        div.className = "rotulo-calle"; div.textContent = nombre;
        this.capaTexto.appendChild(div);
        const [x, z] = this.local((la1 + la2) / 2, (lo1 + lo2) / 2);
        return { div, x, z };
      });
      if (!this.divCalles.length) this.divCalles = null;
    }
    for (const c of this.divCalles || []) {
      v.set(c.x, 1, c.z).project(this.camara);
      const visible = cerca && v.z < 1 && Math.abs(v.x) < 1.05 && Math.abs(v.y) < 1.05;
      c.div.hidden = !visible;
      if (visible) c.div.style.transform = `translate(-50%,-50%) translate(${(v.x + 1) / 2 * w}px,${(1 - v.y) / 2 * h}px)`;
    }
  }

  /** Vuelve a la vista general de la zona. */
  encuadrar() {
    this.siguiendo = null;
    this.controles.target.set(0, 0, 0);
    this.camara.position.set(-260, ALTURA_CAMARA_INICIAL, 420);
  }
}
