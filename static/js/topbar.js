/* ============================================================
   topbar.js - v3.6-ui
   ============================================================
   Lógica mínima para abrir/cerrar los grupos desplegables del
   topbar. No depende de jQuery ni de otros JS. Se carga en
   base.html vía la línea <script src="...topbar.js">.

   Comportamiento:
     - Click en el botón del grupo: toggle el dropdown
     - Click fuera de cualquier grupo: cierra todos
     - Esc: cierra todos
     - Click en un item del dropdown: cierra (la navegación lo hace)
   ============================================================ */
(function () {
    'use strict';

    function closeAll(except) {
        document.querySelectorAll('.tab-group.open').forEach(function (g) {
            if (g !== except) {
                g.classList.remove('open');
                var btn = g.querySelector('.tab-group-btn');
                if (btn) btn.setAttribute('aria-expanded', 'false');
            }
        });
    }

    function toggle(group) {
        var willOpen = !group.classList.contains('open');
        closeAll(group);
        if (willOpen) {
            group.classList.add('open');
            var btn = group.querySelector('.tab-group-btn');
            if (btn) btn.setAttribute('aria-expanded', 'true');
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        // Click en el botón de cada grupo
        document.querySelectorAll('.tab-group-btn').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                var group = btn.closest('.tab-group');
                if (group) toggle(group);
            });
        });

        // Click fuera = cierra todo
        document.addEventListener('click', function (e) {
            if (!e.target.closest('.tab-group')) {
                closeAll(null);
            }
        });

        // Escape = cierra todo
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closeAll(null);
        });
    });
})();
