# Guion de Tyrone · Exposición del interciclo (RVH)

Tus diapositivas son las azules: la 2 a la 5 (unos 2 minutos) y la 20, la demo (1 minuto y medio).
Lo que va entre comillas es lo que dices; lo demás son indicaciones.

## Antes de empezar (5 minutos antes)

- Abre el visor en `e-sert.tesisucuenca.com`, escribe la clave de la demo y pulsa **Iniciar**, con
  50 % de usuarios y ritmo 2×. Deja que corra mientras hablan los demás.
- Ten abierta `sumo.tesisucuenca.com` en otra pestaña, por si el profesor pregunta por SUMO.
- En la presentación, pulsa **R** para poner el cronómetro de 10 minutos en cero.

## Diapositiva 2 · El problema en una frase

«Empecemos por el problema. En el Centro Histórico de Cuenca, buscar parqueo obliga a dar vueltas a
la manzana, y eso cuesta tiempo, distancia y CO₂. No es algo solo de aquí: Shoup reunió dieciséis
estudios en los que encontrar puesto en la calle tomaba entre tres minutos y medio y catorce minutos.
En nuestra simulación del Centro, sin ninguna ayuda, un auto busca en promedio siete minutos, recorre
casi un kilómetro y medio y emite unos ochocientos cuarenta gramos de CO₂ solo buscando. Esa es
nuestra línea base.»

## Diapositiva 3 · El lazo

«El proyecto sigue el lazo que pide el examen. El dato son los puestos y el GPS del teléfono. El
modelo es un Random Forest que dice si el conductor camina o maneja; eso lo explica Pablo. La acción es
guiar el auto al puesto libre con TraCI y cobrar desde la app; eso lo explica Miguel. La medida es el
tiempo, la distancia y el CO₂ de búsqueda frente a la línea base; eso lo presenta Freddy. Y la
visualización es el visor 3D y la app, que voy a mostrar al final en vivo. Todo corre en un solo
servidor.»

## Diapositiva 4 · Puestos sin datos de la EMOV

«Un punto importante: pedimos a la EMOV la ubicación y los códigos de los puestos SERT, pero no
llegaron a tiempo. Por eso los generamos nosotros, como datos sintéticos justificados, que es lo que
permite el examen. Las reglas son simples: solo calles tarifadas con nombre, del lado derecho, cinco
metros y medio por puesto y ocho metros libres en cada esquina, porque en la esquina no se estaciona.»

## Diapositiva 5 · De OpenStreetMap a los puestos

«El proceso fue este: bajamos el mapa del Centro de OpenStreetMap, lo convertimos en red de SUMO con
netconvert, filtramos las calles SERT y creamos un área de parqueo por cada tramo de cuadra. Salieron
seiscientas diez áreas, con seis mil ciento noventa y cuatro puestos en ciento tres calles. Cada área
tiene un código del cero cero uno al seiscientos diez, que es el que el conductor escribe en la app.
Lo importante es que todo el sistema lee un solo archivo, puestos punto csv. Cuando la EMOV nos dé su
lista, solo cambiamos ese archivo, sin tocar el código. Ahora Freddy les explica SUMO y TraCI.»

## Diapositiva 20 · Demostración en vivo

«Ahora lo vemos funcionando. Les pido que alguien escanee este código QR.»

Mientras escanean, señala el visor 3D:

«Esto es el visor en 3D: los edificios del Centro, las calles, el Parque Calderón, los puestos en
verde si tienen espacio y en rojo si están llenos, y cada auto con el color de su estado.»

Pasos:

1. «Cada persona elige un usuario; todos empiezan con diez dólares.»
2. «Pone su ubicación en el mapa y pulsa Buscar parqueadero cercano. En ese momento SUMO crea su auto
   y lo guía por la ruta de manejo más corta.» Haz clic en su nombre en el visor para que la cámara
   lo siga.
3. «Cuando llega, elige cuánto tiempo se queda. El cobro es inmediato: veinticinco centavos por cada
   media hora.» Muestra la pestaña Billetera.
4. «Ahora el conductor se baja: aparece el punto azul, que es él caminando.»
5. «Cuando pulsa Me voy, regresa a su auto, la inteligencia artificial detecta que ya va manejando y
   cierra la sesión sola: el puesto vuelve a verde y la app vuelve al inicio.»

Cierre: «Eso es e-sert. Gracias.»

## Si algo falla

Si la red falla, cambia el visor a **2D** con el botón de arriba a la derecha, o muestra el recorrido
en las diapositivas de Miguel.

## Preguntas que te pueden tocar

- **¿Por qué no usaron los datos reales?** Porque la EMOV no los entregó a tiempo. Los generamos con
  reglas documentadas y el sistema está preparado para cambiar solo el archivo de puestos.
- **¿Cómo validan los puestos?** Las calles se revisaron contra la ordenanza SERT. Falta comparar con
  un conteo en una calle; está declarado como pendiente.
- **¿Dónde se puede replicar?** En GitHub, con la etiqueta v1.0-interciclo. Hay un script que repite
  las corridas y otro que regenera las figuras.
