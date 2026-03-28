# Explicación del Enfoque y Decisiones Técnicas

## 1. Enfoque General

El objetivo del sistema es democratizar el acceso a datos operacionales de Rappi mediante un asistente conversacional impulsado por IA, además de automatizar la generación de insights accionables. Para lograrlo, diseñé una arquitectura modular enfocada en:

- Simplicidad de implementación
- Escalabilidad futura
- Separación clara de responsabilidades
- Facilidad de mantenimiento

El sistema se divide en cuatro capas principales:

1. **Data Layer** — Ingesta y manejo de datasets  
2. **Query Layer (Agent)** — Interpretación de lenguaje natural  
3. **Insights Layer** — Generación automática de hallazgos  
4. **Report & Visualization Layer** — Presentación de resultados  

Este enfoque modular permite evolucionar cada componente de forma independiente.

---

## 2. Decisiones Técnicas Clave

### 2.1 Uso de Python + Pandas para Análisis de Datos

**Decisión:** Utilizar Python y Pandas como motor principal de análisis.

**Justificación:**

- Pandas es altamente eficiente para datasets tabulares
- Permite análisis complejos con bajo overhead
- Fácil integración con LLMs
- Ideal para prototipos rápidos y sistemas analíticos

**Trade-off:**

- No ideal para datasets extremadamente grandes  
- Escalable a futuro mediante DuckDB, Polars o warehouse (BigQuery, Snowflake)

---

### 2.2 Arquitectura Basada en FastAPI

**Decisión:** Utilizar FastAPI como backend principal.

**Justificación:**

- Alto rendimiento
- Fácil creación de endpoints
- Compatible con async
- Documentación automática
- Ideal para servicios AI

**Endpoints Principales:**

- `/chat` → Bot conversacional
- `/insights` → Generación de insights
- `/chart` → Generación de visualizaciones
- `/report` → Reporte ejecutivo

---

### 2.3 Uso de LLM para Traducción de Lenguaje Natural a Análisis

**Decisión:** Utilizar un LLM para interpretar preguntas en lenguaje natural.

**Justificación:**

Permite resolver:

- Queries complejas
- Análisis multivariable
- Inferencias
- Comparaciones dinámicas
- Memoria conversacional

El flujo es:

Usuario → LLM → Query estructurada → Pandas → Resultado → LLM → Respuesta

Este enfoque evita crear reglas rígidas y permite mayor flexibilidad.

---

### 2.4 Sistema de Insights Automáticos

**Decisión:** Separar el motor de insights del bot conversacional.

**Justificación:**

Permite:

- Ejecución programada
- Generación de reportes automáticos
- Análisis independiente del usuario

Tipos de insights implementados:

- Anomalías (>10% cambios)
- Tendencias negativas (3+ semanas)
- Benchmarking entre zonas
- Correlaciones entre métricas
- Oportunidades de crecimiento

---

### 2.5 Generación de Reportes Ejecutivos

**Decisión:** Generar reportes estructurados en HTML/Markdown.

**Justificación:**

- Fácil exportación
- Compatible con PDF
- Fácil lectura para stakeholders
- Bajo overhead técnico

Estructura del reporte:

- Resumen ejecutivo
- Insights por categoría
- Recomendaciones accionables
- Visualizaciones

---

### 2.6 Visualización de Datos

**Decisión:** Generar metadata de gráficos en vez de gráficos directamente.

**Justificación:**

- Separación frontend/backend
- Mayor flexibilidad
- Compatible con múltiples librerías (Chart.js, Plotly, etc.)

Tipos de gráficos soportados:

- Tendencias (línea)
- Comparaciones (barra)
- Distribuciones

---

## 3. Escalabilidad del Sistema

El sistema fue diseñado para escalar en varias dimensiones:

### Escalabilidad de Datos

Futuras mejoras:

- DuckDB
- Polars
- Data Warehouse (BigQuery / Snowflake)

---

### Escalabilidad del LLM

Posibles mejoras:

- RAG con métricas históricas
- Memoria conversacional persistente
- Multi-agent architecture

---

### Escalabilidad de Infraestructura

Opciones futuras:

- Docker
- Kubernetes
- Serverless deployment

---

## 4. Trade-offs Principales

| Decisión | Ventaja | Desventaja |
|----------|---------|------------|
| Pandas en memoria | Simple y rápido | Limitado en datasets grandes |
| LLM-based querying | Flexible | Mayor costo |
| FastAPI | Alto rendimiento | Requiere backend |
| Modular architecture | Escalable | Más archivos |

---

## 5. Consideraciones de Costos

Costos principales:

- LLM usage (OpenAI / similar)
- Infraestructura (opcional)

Estimación aproximada:

Estamos usando un modelo eficiente (gpt-5.4-mini) con un costo de $0.75 por millón de tokens de entrada y $4.50 por millón de tokens de salida.

El sistema es eficiente en costos al:

- Reutilizar resultados
- Minimizar llamadas LLM
- Procesar localmente con pandas

---

## 6. Limitaciones Actuales

- Dataset en memoria
- Sin autenticación de usuarios
- Sin persistencia conversacional
- Sin deployment cloud (opcional)

---

## 7. Próximos Pasos

Mejoras potenciales:

- Deployment en cloud
- UI más robusta
- Alertas automáticas
- Programación de reportes
- Memoria conversacional persistente
- Sistema multi-agente

---

## 8. Conclusión

El sistema fue diseñado priorizando:

- Simplicidad
- Escalabilidad
- Flexibilidad
- Valor de negocio

Este enfoque permite entregar una solución funcional rápidamente, con una arquitectura preparada para evolucionar hacia un sistema analítico más robusto y escalable.
