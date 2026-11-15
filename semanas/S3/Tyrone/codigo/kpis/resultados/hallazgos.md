# Hallazgos de la matriz de experimentos

Fuente: `kpis/resultados/experimentos.csv` (24 corridas; réplica = semilla; IC 95 % t de Student entre semillas, con n = 3 los intervalos son anchos y así se reportan). Se regenera con `python -m kpis.analisis`.

1. Con la búsqueda a ciegas (0 % de usuarios con app), el tiempo de búsqueda medio es 436 s (IC 95 %: 382–490 s, n = 3 semillas).
2. Con 20 % de usuarios (rf), el tiempo de búsqueda cambia −1,5 % (IC 95 %: −16,7 a +13,8 %) frente a la búsqueda a ciegas, pareado por semilla (n = 3). El IC cruza el cero: no hay mejora demostrada.
3. Con 50 % de usuarios (rf), el tiempo de búsqueda cambia −0,1 % (IC 95 %: −8,8 a +8,6 %) frente a la búsqueda a ciegas, pareado por semilla (n = 3). El IC cruza el cero: no hay mejora demostrada.
4. Con 80 % de usuarios (rf), el tiempo de búsqueda cambia +2,4 % (IC 95 %: −2,5 a +7,2 %) frente a la búsqueda a ciegas, pareado por semilla (n = 3). El IC cruza el cero: no hay mejora demostrada.
5. Con 50 % de usuarios (rf), la distancia de búsqueda cambia −1,2 % (IC 95 %: −6,5 a +4,0 %) frente a la búsqueda a ciegas, pareado por semilla (n = 3). El IC cruza el cero: no hay mejora demostrada.
6. Con 50 % de usuarios (rf), el CO₂ de búsqueda cambia +1,3 % (IC 95 %: −6,5 a +9,0 %) frente a la búsqueda a ciegas, pareado por semilla (n = 3). El IC cruza el cero: no hay mejora demostrada.
7. La ocupación media de la hora pico va de 87,4 % a 87,5 % entre escenarios: la app no cambia cuántos autos estacionan, sino cuánto buscan.
8. Con 50 % de usuarios, las falsas liberaciones son 86,9 por 100 sesiones con el umbral (IC 95 %: 84,1–89,7) y 0,0 con el RF (0,0–0,0); t pareada p = 0,000, p de Holm = 0,000 (3 comparaciones).
9. La precisión del mapa de ocupación pasa de 58,0 % (IC 95 %: 57,4–58,6 %) al 0 % a 57,9 % (56,7–59,1 %) con 80 % de usuarios.
10. La mediana del retardo de cierre de la sesión al 50 % es rf: 18,0 s (IC 95 %: 15,5–20,5); umbral: 26,7 s (IC 95 %: 11,5–41,8).
