# Native Migration Roadmap (Actualizado)

## Objetivo
Consolidar `native_app/` como única aplicación activa y cerrar la etapa legacy web/backend.

## Pendiente real (no completado)
1. Consolidar en `develop` los cambios ya implementados en ramas de trabajo:
   - arranque no bloqueante de UI (sync en background),
   - smoke tests de arranque + inicialización de DB,
   - validación de integridad de eventos antes de persistencia.
2. Revisar cada rama nueva antes de mergear a `develop`:
   - si aporta cambios útiles para el objetivo actual, integrar esos commits en `develop`,
   - si no aporta valor real, desechar la rama.
3. Cerrar decisión de UX sobre navegación por secciones (`tabs`/sidebar) para evitar reworks repetidos.
4. Ajustar mensajes de error de captura/red para que sean accionables en UI (TLS/handshake/lock).

## Alcance ya cubierto
- Núcleo nativo operativo (`native_app/app/main.py`).
- Captura por proxy y persistencia de flujo.
- Tabla de logger de batallas con búsqueda/paginación y detalle.
- Base de pruebas de captura/persistencia/retención.
