/* ============================================================================
   Buscador del sitio — el control único de la superficie.

   Una sola consulta filtra lo que haya en la página (las bandas de fase en la
   portada, las filas en las páginas de fase), señala cuántos recursos del
   programa coinciden, y sobrevive al saltar de una fase a otra: viaja en la URL
   y en sessionStorage. Nunca recarga la página.
   ========================================================================= */
(function () {
  'use strict';

  var CLAVE = 'grd:consulta';
  var campo = document.getElementById('buscador');
  if (!campo) return;

  var barra = campo.closest('.consulta');
  var limpiar = document.getElementById('limpiar');
  var salida = document.getElementById('resultados');
  var recuento = document.getElementById('recuento');
  var indice = window.INDICE || [];
  var faseActual = document.body.getAttribute('data-fase') || '';

  function normalizar(texto) {
    return (texto || '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '');
  }

  var items = indice.map(function (i) {
    return { d: i, clave: normalizar(i.t + ' ' + i.d) };
  });

  var bandas = [].slice.call(document.querySelectorAll('[data-fase-banda]'));
  var filas = [].slice.call(document.querySelectorAll('[data-buscable]'));
  var bloques = [].slice.call(document.querySelectorAll('[data-bloque]'));
  var total = indice.length || filas.length;

  /* ------------------------------------------------------------ resultados */

  function pintarResultados(hallados, q) {
    if (!salida) return;
    salida.innerHTML = '';
    if (!q) return;

    if (!hallados.length) {
      var vacio = document.createElement('li');
      vacio.className = 'vacio';
      vacio.textContent = 'Ningún recurso del programa coincide con «' + campo.value + '».';
      salida.appendChild(vacio);
      return;
    }

    var TOPE = 14;
    hallados.slice(0, TOPE).forEach(function (h) {
      var li = document.createElement('li');
      var a = document.createElement('a');
      a.href = h.d.u;
      a.target = '_blank';
      a.rel = 'noopener';
      a.innerHTML = '<span class="tipo"></span><span class="que"></span><span class="donde"></span>';
      a.querySelector('.tipo').textContent = h.d.k;
      a.querySelector('.que').textContent = h.d.t;
      a.querySelector('.donde').textContent = h.d.d;
      li.appendChild(a);
      salida.appendChild(li);
    });

    // Una lista recortada en silencio parece completa: se dice el recorte.
    if (hallados.length > TOPE) {
      var mas = document.createElement('li');
      mas.className = 'mas';
      mas.textContent = 'Mostrando ' + TOPE + ' de ' + hallados.length +
        ' coincidencias. Afina la búsqueda o entra por la fase.';
      salida.appendChild(mas);
    }
  }

  /* --------------------------------------------------------------- recuento */

  function fuerte(texto) {
    var b = document.createElement('b');
    b.textContent = texto;
    return b;
  }

  function pintarRecuento(n, q) {
    if (!recuento) return;
    recuento.textContent = '';
    if (!q) {
      recuento.textContent = recuento.getAttribute('data-reposo');
      return;
    }
    // Se compone con nodos de texto: `campo.value` viene del parámetro ?q= de
    // la URL, así que interpolarlo en innerHTML sería un XSS reflejado.
    recuento.appendChild(fuerte(String(n)));
    recuento.appendChild(document.createTextNode(' de '));
    recuento.appendChild(fuerte(String(total)));
    recuento.appendChild(document.createTextNode(
      ' recursos coinciden con «' + campo.value + '»'));
  }

  /* ----------------------------------------------------------------- filtro */

  function aplicar(q, animar) {
    var norm = normalizar(q.trim());
    var hallados = norm
      ? items.filter(function (i) { return i.clave.indexOf(norm) !== -1; })
      : [];

    if (barra) barra.classList.toggle('tiene-texto', !!q);

    // Bandas de fase: cada una dice cuántas de sus piezas coinciden, y el
    // tablero se reordena para poner delante la fase con más. Ninguna banda se
    // borra: una fase sin coincidencias se dibuja apagada, que es el dato.
    bandas.forEach(function (b) {
      var n = norm
        ? hallados.filter(function (h) {
          return String(h.d.f) === b.getAttribute('data-fase-banda');
        }).length
        : 0;
      var marca = b.querySelector('[data-coincide]');
      if (marca) {
        marca.textContent = norm
          ? (n === 1 ? '1 coincide' : n + ' coinciden')
          : '';
        marca.classList.toggle('oculto', !norm);
      }
      b.classList.toggle('apagada', !!norm && n === 0);
      b.style.order = norm ? String(-n) : '';
    });

    // Filas de la página: se ocultan las que no coinciden, y con ellas los
    // bloques que se quedan sin contenido.
    filas.forEach(function (f) {
      var ok = !norm || normalizar(f.getAttribute('data-buscable')).indexOf(norm) !== -1;
      f.classList.toggle('oculto', !ok);
    });
    bloques.forEach(function (b) {
      b.classList.toggle('oculto', b.querySelectorAll('[data-buscable]:not(.oculto)').length === 0);
    });

    pintarResultados(hallados, norm);
    pintarRecuento(norm ? hallados.length : total, norm);

    // El único momento de movimiento autorizado: el tablero se asienta.
    if (animar && norm && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      var vivos = bandas.concat(filas).filter(function (el) {
        return !el.classList.contains('oculto');
      });
      vivos.slice(0, 12).forEach(function (el) {
        el.classList.remove('asienta');
        void el.offsetWidth;
        el.classList.add('asienta');
      });
    }

    recordar(q);
  }

  /* ------------------------------------------------------------- memoria */

  function recordar(q) {
    try {
      if (q) sessionStorage.setItem(CLAVE, q);
      else sessionStorage.removeItem(CLAVE);
    } catch (e) { /* modo privado: la consulta simplemente no se recuerda */ }

    // La consulta viaja en la URL, sin recargar, para que sobreviva al salto.
    try {
      var url = new URL(window.location.href);
      if (q) url.searchParams.set('q', q);
      else url.searchParams.delete('q');
      history.replaceState(null, '', url);
    } catch (e) { /* navegador sin URL/history: se pierde solo la URL */ }

    // Los enlaces internos se llevan la consulta consigo.
    [].forEach.call(document.querySelectorAll('[data-lleva-consulta]'), function (a) {
      var base = a.getAttribute('data-lleva-consulta');
      a.setAttribute('href', q ? base + '?q=' + encodeURIComponent(q) : base);
    });
  }

  function consultaInicial() {
    try {
      var deUrl = new URL(window.location.href).searchParams.get('q');
      if (deUrl) return deUrl;
    } catch (e) { /* sigue con la memoria de sesión */ }
    try { return sessionStorage.getItem(CLAVE) || ''; } catch (e) { return ''; }
  }

  /* ------------------------------------------------------------- arranque */

  var pendiente;
  campo.addEventListener('input', function () {
    clearTimeout(pendiente);
    pendiente = setTimeout(function () { aplicar(campo.value, true); }, 80);
  });

  campo.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape') { campo.value = ''; aplicar('', false); }
  });

  if (limpiar) {
    limpiar.addEventListener('click', function () {
      campo.value = '';
      aplicar('', false);
      campo.focus();
    });
  }

  var inicial = consultaInicial();
  if (inicial) campo.value = inicial;
  aplicar(inicial, false);

  // En la portada, y solo con teclado físico, el cursor arranca en el buscador:
  // el aprendiz que ya sabe qué busca escribe sin tocar nada. En móvil no, para
  // no levantar el teclado encima del tablero. En una página de fase tampoco: la
  // consulta heredada ya viene aplicada y se deja leer.
  var tecladoFisico = matchMedia('(pointer: fine)').matches && window.innerWidth >= 700;
  if (!inicial && !faseActual && tecladoFisico) campo.focus({ preventScroll: true });
})();
