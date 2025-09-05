

# **Implementación de un Sistema Multi-Agente Avanzado para E-commerce con LangGraph**

## **I. Resumen Ejecutivo: Un Plan Estratégico para una Plataforma de E-commerce Agéntica con LangGraph**

Este informe presenta un plan técnico definitivo para el diseño e implementación de un sistema de inteligencia artificial conversacional avanzado para una plataforma de e-commerce, utilizando el framework LangGraph. La recomendación central es la adopción de un **Sistema Multi-Agente Jerárquico** basado en la **Arquitectura de Supervisor (con Llamada a Herramientas)**, implementado a través de las librerías langgraph y langgraph-supervisor. Este modelo arquitectónico ofrece el equilibrio óptimo entre control, flexibilidad y escalabilidad, abordando directamente la necesidad de enrutar dinámicamente las consultas de los usuarios a agentes especializados.

La arquitectura propuesta se fundamenta en cuatro pilares estratégicos:

1. **Orquestación Centralizada:** Un agente Supervisor actúa como el centro neurálgico del sistema, analizando la intención del usuario y delegando tareas de manera inteligente a un equipo de agentes trabajadores especializados.  
2. **Agentes Trabajadores Especializados:** Cada agente (por ejemplo, Consultas de Producto, Gestión de Pedidos, Soporte General) es un experto en su dominio, equipado con un conjunto específico de herramientas y acceso a fuentes de conocimiento relevantes, como bases de datos de productos o APIs de sistemas de gestión de pedidos.  
3. **Conversaciones con Estado (Stateful):** Se utiliza el robusto mecanismo de persistencia de LangGraph, conocido como Checkpointer, para garantizar conversaciones fluidas y de múltiples turnos. Esto no solo proporciona una memoria conversacional sino que también asegura la tolerancia a fallos, permitiendo que las interacciones se reanuden desde el último estado guardado.1  
4. **Diseño Modular y Escalable:** Los agentes trabajadores se encapsulan como grafos autocontenidos (Subgraphs), promoviendo el desarrollo, las pruebas y el mantenimiento independientes. Esta modularidad es clave para la escalabilidad a largo plazo del sistema.3

Desde una perspectiva de valor de negocio, esta arquitectura transforma un chatbot estándar en un sistema dinámico e inteligente capaz de resolver solicitudes complejas y multidominio de los usuarios. El resultado es una mejora significativa en la experiencia del cliente, una reducción en la carga de trabajo del soporte humano y una base tecnológica sólida para la futura incorporación de funcionalidades impulsadas por IA.

Este documento guiará al lector a través de un recorrido completo, desde los principios fundamentales de LangGraph hasta una implementación detallada y lista para producción, culminando con recomendaciones estratégicas para el despliegue, la monitorización y el mantenimiento del sistema.

## **II. Principios Fundamentales de LangGraph para Flujos de Trabajo Agénticos Cíclicos**

Para construir sistemas de agentes efectivos, es imperativo comprender el cambio de paradigma que introduce LangGraph. Su diseño aborda las limitaciones inherentes de los modelos de ejecución lineal y proporciona las herramientas para crear aplicaciones cíclicas y con estado, que son la base del comportamiento agéntico.

### **El Cambio de Paradigma de los DAGs a las Máquinas de Estado**

Los primeros frameworks para la construcción de aplicaciones con Modelos de Lenguaje Grandes (LLMs), incluyendo las versiones iniciales de LangChain, se basaban predominantemente en Grafos Acíclicos Dirigidos (DAGs). Si bien son efectivos para procesos secuenciales y predecibles, los DAGs presentan una limitación fundamental para el desarrollo de agentes: carecen de la capacidad inherente de crear bucles o ciclos. El comportamiento de un agente se define por un ciclo de "razonamiento-acción" (ReAct): el agente razona sobre un problema, elige una acción (como llamar a una herramienta), observa el resultado de esa acción y luego vuelve a razonar para decidir el siguiente paso.5 Este proceso es intrínsecamente cíclico.

LangGraph fue diseñado específicamente para superar esta limitación, permitiendo la construcción de aplicaciones cíclicas y con estado.6 El concepto central es el de una máquina de estado. En este modelo, la aplicación se define como un grafo donde los nodos representan unidades de cómputo (funciones o agentes) y las aristas representan las transiciones entre estos nodos. A diferencia de un DAG, estas aristas pueden formar bucles, permitiendo que el control fluya de un nodo a otro y de vuelta al mismo nodo o a uno anterior, modelando así el ciclo de razonamiento del agente.6

### **Componentes Centrales de una Aplicación LangGraph**

Toda aplicación construida con LangGraph se compone de un conjunto de elementos fundamentales que definen su estructura y comportamiento.

#### **Estado (StateGraph)**

El estado es la estructura de datos central que se comparte y se pasa entre todos los nodos del grafo. Actúa como la memoria de trabajo del sistema. Típicamente, se define como un TypedDict de Python, que especifica el esquema de los datos que se mantendrán a lo largo de la ejecución.8 Para un chatbot, un estado común incluye una clave

messages que contiene una lista de todos los mensajes de la conversación.

Un concepto clave en la gestión del estado es el uso de Annotated y los **Reductores** (Reducers). Un reductor es una función que define cómo se actualiza un campo del estado. Por ejemplo, la función preconstruida add\_messages especifica que los nuevos mensajes deben añadirse a la lista existente en lugar de sobrescribirla. Los campos del estado que no tienen un reductor se sobrescriben con cada actualización.8 Esta distinción es crucial para gestionar correctamente el historial conversacional.

#### **Nodos**

Los nodos son las unidades de cómputo del grafo. Representan una función, un LLM, una llamada a una herramienta o cualquier otro objeto ejecutable (Runnable). Cada nodo recibe el estado actual del grafo como entrada y devuelve un diccionario que representa una actualización a ese estado.6

#### **Aristas**

Las aristas definen el flujo de control, conectando los nodos para determinar la secuencia de ejecución. LangGraph incluye puntos de entrada y salida especiales, START y END. Más importante aún, soporta **Aristas Condicionales** (Conditional Edges). Estas aristas permiten que el flujo del grafo se bifurque dinámicamente basándose en el estado actual. Por ejemplo, una arista condicional puede inspeccionar la última respuesta de un LLM; si la respuesta contiene una llamada a una herramienta, la arista dirige el flujo al nodo de herramientas; de lo contrario, lo dirige al nodo final (END).10 Esta capacidad es fundamental para el enrutamiento dinámico en sistemas de agentes.

#### **Compilación**

Una vez que se han definido el estado, los nodos y las aristas, el grafo se compila usando el método workflow.compile(). Este paso transforma la definición declarativa del grafo en un objeto ejecutable (Pregel), que está listo para procesar entradas.9

### **LangGraph como un Framework de "Arquitectura Cognitiva"**

La construcción de una aplicación con LangGraph trasciende la mera programación de un flujo de trabajo; es, en esencia, el diseño explícito de una arquitectura cognitiva a medida. Los componentes del framework no son solo constructos de software, sino que se pueden mapear directamente a los elementos de un proceso de razonamiento.

El Estado del grafo funciona como la "memoria de trabajo" del agente, manteniendo el contexto actual de la tarea. Los Nodos representan las diversas "funciones cognitivas" que el agente puede ejecutar: razonamiento (una llamada a un LLM), percepción (la salida de una herramienta que interactúa con el mundo exterior) o recuperación de memoria (una consulta a una base de datos vectorial). Finalmente, las Aristas Condicionales encarnan el "proceso de toma de decisiones", dictando qué función cognitiva se debe emplear a continuación en función del estado actual de la memoria de trabajo.

Desde esta perspectiva, el poder de LangGraph no reside en proporcionar agentes preconstruidos y monolíticos, sino en ofrecer el control de bajo nivel necesario para definir con precisión cómo un agente percibe, razona y actúa dentro de un bucle cíclico y con estado. Es este control granular lo que lo diferencia de los frameworks de agentes más "caja negra" y lo hace excepcionalmente adecuado para tareas complejas y de nivel empresarial que requieren fiabilidad, auditabilidad y un comportamiento personalizado.12

## **III. Inmersión Arquitectónica: El Modelo Supervisor para la Orquestación de Tareas de E-commerce**

La elección de la arquitectura multi-agente es una decisión fundamental que impactará la escalabilidad, mantenibilidad y fiabilidad del sistema. Para una aplicación de e-commerce, donde la claridad del flujo de control y la previsibilidad son primordiales, el modelo Supervisor emerge como la opción superior.

### **Análisis de Arquitecturas Multi-Agente**

LangGraph permite la implementación de varias arquitecturas de colaboración entre agentes, cada una con sus propias fortalezas y debilidades.13

* **Red (Network):** En esta arquitectura, cada agente puede comunicarse directamente con cualquier otro agente. Si bien ofrece la máxima flexibilidad, puede conducir rápidamente a un comportamiento caótico e impredecible, a menudo denominado "chatter" de agentes. El flujo de control es difícil de seguir y depurar, lo que lo hace inadecuado para una aplicación orientada al cliente que exige respuestas consistentes y fiables.  
* **Jerárquica (Hierarchical):** Este modelo organiza a los agentes en una estructura de árbol, con supervisores que gestionan equipos de agentes, y potencialmente supervisores de nivel superior que gestionan a otros supervisores. Es una arquitectura extremadamente escalable, ideal para organizaciones de agentes muy grandes y complejas, como la simulación de una empresa entera. Sin embargo, para los requisitos iniciales de una plataforma de e-commerce, representa una complejidad innecesaria, aunque se perfila como una vía de crecimiento futuro.13  
* **Supervisor:** En esta arquitectura, un agente orquestador central se comunica con un conjunto de agentes trabajadores especializados. La comunicación sigue un patrón de "hub-and-spoke": los trabajadores solo informan al supervisor, y el supervisor es el único que delega tareas a los trabajadores.13 Este modelo proporciona un flujo de control claro, un comportamiento predecible y una depuración significativamente más sencilla. Se alinea perfectamente con el problema de enrutar consultas de usuarios a diferentes dominios funcionales (productos, pedidos, etc.).

La siguiente tabla resume la comparación y justifica la elección del modelo Supervisor.

**Tabla 1: Comparación de Arquitecturas Multi-Agente en LangGraph**

| Arquitectura | Flujo de Control | Patrón de Comunicación | Escalabilidad | Depurabilidad | Idoneidad para Chatbot de E-commerce |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **Supervisor** | Centralizado, de arriba hacia abajo | Hub-and-Spoke | Alta | Alta | **Excelente**. Proporciona control y previsibilidad. |
| **Jerárquica** | Centralizado por niveles | Árbol jerárquico | Muy Alta | Media | Buena, pero potencialmente excesiva para el inicio. |
| **Red** | Distribuido, emergente | Todos con todos | Media | Baja | Pobre. Riesgo de comportamiento caótico. |

### **El Patrón Supervisor (con Llamada a Herramientas): El Enfoque Recomendado**

Una variante particularmente poderosa y elegante del modelo Supervisor es aquella en la que los agentes trabajadores se exponen al supervisor *como si fueran herramientas*.13 En este patrón, el agente supervisor es impulsado por un LLM con capacidad de llamada a herramientas.

El proceso funciona de la siguiente manera:

1. El supervisor recibe la consulta del usuario y el historial de la conversación.  
2. El LLM del supervisor, guiado por un prompt cuidadosamente diseñado, analiza la entrada.  
3. En lugar de generar una respuesta directamente, el LLM determina qué agente especializado es el más adecuado para manejar la consulta y emite una llamada a una "herramienta" que representa a ese agente (por ejemplo, transfer\_to\_product\_agent).  
4. El framework de LangGraph intercepta esta llamada a la herramienta y transfiere el control al agente trabajador correspondiente.

Este enfoque traslada la lógica de enrutamiento compleja de las aristas condicionales codificadas en el grafo a las capacidades de razonamiento del LLM del supervisor. La clave del éxito de este patrón reside en la ingeniería del prompt del supervisor.18

### **La Mecánica de las Transferencias de Control (Handoffs)**

Una "transferencia" o "handoff" es el proceso técnico de ceder el control y pasar el estado de un agente a otro.13 En el modelo Supervisor con llamada a herramientas, este proceso es gestionado en gran medida por la librería

langgraph-supervisor, que crea automáticamente las herramientas de transferencia para cada agente trabajador.16

A un nivel más bajo, LangGraph implementa estas transferencias dinámicas utilizando el objeto Command. Un nodo en el grafo puede devolver un objeto Command que especifica dos cosas: una actualización al estado del grafo y el nombre del siguiente nodo a ejecutar (goto). Esta es la primitiva que permite el enrutamiento dinámico y el control explícito sobre el flujo de ejecución del grafo.13 Por ejemplo, un nodo supervisor podría devolver

Command(goto="product\_agent", update={"messages": \[...\]}) para dirigir el flujo al agente de productos.

## **IV. Implementación (Parte 1): Construcción de los Agentes Trabajadores Especializados de E-commerce**

La filosofía de diseño para los agentes trabajadores es la especialización y la autonomía. Cada agente debe ser un experto en un único dominio funcional, encapsulando las herramientas y la lógica necesarias para cumplir con su responsabilidad. Utilizaremos la función create\_react\_agent de LangGraph, que proporciona una implementación estándar y robusta del bucle ReAct (Reason+Act).18

### **El Agente de Consultas de Producto: Un Especialista con RAG**

Este agente debe responder preguntas sobre el catálogo de productos, como especificaciones, características, precios y disponibilidad. Dado que esta información es dinámica y reside en una base de datos externa, el conocimiento del LLM no es suficiente. Por lo tanto, este agente es un candidato ideal para una implementación de **Generación Aumentada por Recuperación (RAG) Agéntica**.10

#### **Definición de Herramientas de Recuperación**

El primer paso es crear una herramienta que permita al agente buscar en el catálogo de productos. Esto implica configurar un almacén de vectores (vector store) que contenga la información de los productos.

1. **Indexación de Datos:** Los datos de los productos (descripciones, especificaciones, etc.) se extraen de la base de datos de e-commerce y se dividen en fragmentos (chunks). Estos fragmentos se convierten en vectores (embeddings) y se almacenan en un almacén de vectores como Chroma, MongoDB Atlas Vector Search o Elasticsearch.10  
2. **Creación del Recuperador:** Se crea un objeto retriever que puede realizar búsquedas de similitud semántica en el almacén de vectores.  
3. **Envoltura como Herramienta:** El retriever se envuelve en una herramienta que el agente puede invocar. La función create\_retriever\_tool de LangChain simplifica este proceso. Es de vital importancia proporcionar una descripción clara y precisa en la herramienta, ya que el agente utilizará esta descripción para decidir cuándo usarla.22

Python

from langchain.tools.retriever import create\_retriever\_tool  
from langchain\_community.vectorstores import Chroma  
from langchain\_openai import OpenAIEmbeddings

\# Suponiendo que 'product\_docs' es una lista de documentos del catálogo  
vectorstore \= Chroma.from\_documents(documents=product\_docs, embedding=OpenAIEmbeddings())  
retriever \= vectorstore.as\_retriever()

product\_retriever\_tool \= create\_retriever\_tool(  
    retriever,  
    "product\_catalog\_search",  
    "Busca y devuelve información sobre las especificaciones, características y precios de los productos en el catálogo."  
)

#### **Estructura del Agente**

Una vez definida la herramienta, se instancia el agente utilizando create\_react\_agent. Se le proporciona el LLM, la lista de herramientas y un prompt de sistema que define su personalidad y su misión.21

Python

from langgraph.prebuilt import create\_react\_agent  
from langchain\_openai import ChatOpenAI

llm \= ChatOpenAI(model="gpt-4o", temperature=0)  
tools \= \[product\_retriever\_tool\]

product\_agent \= create\_react\_agent(  
    llm,  
    tools,  
    prompt="Eres un experto en nuestro catálogo de productos. Utiliza la herramienta 'product\_catalog\_search' para responder a cualquier pregunta sobre las especificaciones, características, precios y disponibilidad de los productos."  
)

### **El Agente de Gestión de Pedidos: Interfaz con APIs de Backend**

Este agente se encarga de consultas relacionadas con el estado de los pedidos, facturas, envíos y devoluciones. Sus herramientas no serán de recuperación, sino clientes directos de las APIs del sistema de gestión de la empresa.

#### **Definición de Herramientas de API**

Se definen funciones de Python que realizan llamadas a las APIs internas. El decorador @tool de LangChain se utiliza para exponer estas funciones como herramientas para el agente. Las docstrings de estas funciones son cruciales, ya que actúan como la documentación que el LLM leerá para entender qué hace cada herramienta y qué parámetros necesita.11

Python

from langchain\_core.tools import tool  
import your\_ecommerce\_api\_client

@tool  
def get\_shipping\_status(order\_id: str) \-\> str:  
    """Utiliza esta herramienta para obtener el estado de envío de un pedido específico, dado su ID de pedido."""  
    try:  
        status \= your\_ecommerce\_api\_client.fetch\_shipping\_status(order\_id)  
        return f"El estado del envío para el pedido {order\_id} es: {status}"  
    except Exception as e:  
        return f"No se pudo encontrar información para el pedido {order\_id}. Error: {e}"

@tool  
def get\_invoice\_details(order\_id: str) \-\> dict:  
    """Obtiene los detalles completos de la factura, incluyendo artículos y total, para un ID de pedido dado."""  
    try:  
        invoice \= your\_ecommerce\_api\_client.fetch\_invoice(order\_id)  
        return invoice  
    except Exception as e:  
        return {"error": f"No se pudo recuperar la factura para el pedido {order\_id}."}

#### **Estructura del Agente**

De manera similar al agente de productos, el agente de pedidos se instancia con create\_react\_agent, proporcionándole el conjunto de herramientas de API y un prompt de sistema adecuado.

Python

order\_management\_tools \= \[get\_shipping\_status, get\_invoice\_details\]

order\_agent \= create\_react\_agent(  
    llm,  
    order\_management\_tools,  
    prompt="Eres un especialista en gestión de pedidos. Utiliza las herramientas disponibles para responder preguntas sobre el estado de los envíos y los detalles de las facturas."  
)

### **El Agente de Soporte General: Punto de Respaldo y Escalación**

Este agente actúa como un comodín, manejando consultas que no encajan en las especializaciones de los otros agentes, como preguntas sobre políticas de la empresa, horarios de atención o problemas que requieren escalación a un humano. Sus herramientas pueden incluir una búsqueda web de propósito general (por ejemplo, con Tavily Search) o una función para crear un ticket de soporte y notificar a un agente humano.21

### **Tabla 2: Especificación de Agentes de E-commerce**

La siguiente tabla sirve como un documento de diseño, resumiendo las responsabilidades, herramientas y dependencias de cada agente. Este enfoque estructurado es invaluable para la planificación del proyecto y la coordinación del equipo de desarrollo.

| Nombre del Agente | Responsabilidades | Herramientas Requeridas | Descripción de la Herramienta (para el LLM) | Dependencia de Backend |
| :---- | :---- | :---- | :---- | :---- |
| **Agente de Consultas de Producto** | Responder preguntas sobre el catálogo de productos (especificaciones, precios, stock). | product\_catalog\_search | "Busca información sobre productos en el catálogo." | Base de Datos de Vectores (Productos) |
| **Agente de Gestión de Pedidos** | Consultar estado de envío, detalles de facturas, gestionar devoluciones. | get\_shipping\_status, get\_invoice\_details | "Obtiene el estado de envío de un pedido.", "Recupera los detalles de una factura." | API del Sistema de Pedidos (ERP/OMS) |
| **Agente de Soporte General** | Atender consultas generales, políticas de la empresa, escalar a soporte humano. | web\_search, create\_support\_ticket | "Busca en la web información general.", "Crea un ticket para soporte humano." | API de Búsqueda Web, Sistema de Ticketing |

## **V. Implementación (Parte 2): Creación del Supervisor Inteligente**

Con los agentes trabajadores especializados ya definidos, el siguiente paso es construir el orquestador que los dirigirá. La librería langgraph-supervisor simplifica enormemente este proceso, abstrayendo la complejidad de la construcción manual del grafo de supervisión.

### **Aprovechando la Librería langgraph-supervisor**

En lugar de definir manualmente los nodos para el supervisor, las aristas condicionales para el enrutamiento y la lógica para manejar las llamadas a herramientas, podemos utilizar la función de alto nivel create\_supervisor. Esta función toma la lista de agentes trabajadores y el modelo del supervisor, y construye automáticamente el grafo de orquestación subyacente.20

El patrón de código principal es notablemente conciso y declarativo 16:

Python

from langgraph\_supervisor import create\_supervisor

\# 'product\_agent', 'order\_agent', y 'general\_support\_agent' son los agentes compilados de la sección anterior.  
\# 'llm' es la instancia del modelo de lenguaje para el supervisor.  
agents \= \[product\_agent, order\_agent, general\_support\_agent\]

\# El prompt del supervisor se define a continuación.  
supervisor\_prompt \= "..." 

workflow \= create\_supervisor(  
    agents=agents,  
    model=llm,  
    prompt=supervisor\_prompt  
)

### **Ingeniería del Prompt de Enrutamiento del Supervisor**

El componente más crítico del supervisor no es el código, sino su prompt. Este prompt es el "cerebro" del sistema de enrutamiento; es el conjunto de instrucciones que el LLM del supervisor utiliza para decidir a qué agente delegar cada tarea. Un prompt bien diseñado es la clave para un comportamiento preciso y fiable.

El prompt debe instruir explícitamente al supervisor sobre cómo tomar decisiones de delegación basadas en la intención del usuario, haciendo referencia a las herramientas de transferencia que create\_supervisor genera automáticamente (por defecto, con el formato transfer\_to\_\<agent\_name\>).18

A continuación se muestra un ejemplo de un prompt de enrutamiento robusto:

Python

supervisor\_prompt \= """  
Eres un supervisor de un equipo de asistentes de IA para una plataforma de e-commerce. Tu trabajo es analizar la consulta del usuario y el historial de la conversación para delegar la tarea al agente correcto.

Tienes acceso a los siguientes agentes, cada uno expuesto como una herramienta:  
\- 'transfer\_to\_product\_agent': Úsalo para preguntas sobre especificaciones de productos, características, precios, comparación entre productos o disponibilidad de stock.  
\- 'transfer\_to\_order\_agent': Úsalo para preguntas relacionadas con un pedido existente, como estado del envío, detalles de la factura, seguimiento de paquetes o iniciar una devolución.  
\- 'transfer\_to\_general\_support\_agent': Úsalo para todas las demás preguntas, incluyendo políticas de la empresa, horarios, o si el usuario solicita hablar con un humano.

Basado en la última consulta del usuario, invoca la herramienta del agente más apropiado. Solo debes responder con la llamada a la herramienta.  
"""

Este prompt es efectivo porque es:

* **Basado en roles:** Define claramente el papel del LLM ("Eres un supervisor...").  
* **Explícito:** Enumera los agentes disponibles y sus responsabilidades exactas.  
* **Directivo:** Indica al LLM exactamente qué hacer ("invoca la herramienta del agente más apropiado") y cómo responder ("Solo debes responder con la llamada a la herramienta").

### **Compilación y Visualización del Grafo Final**

El último paso es compilar el flujo de trabajo del supervisor y, opcionalmente, visualizar su estructura para facilitar la depuración y la comprensión. La compilación se realiza de la misma manera que con cualquier grafo de LangGraph, pero es en este paso donde integramos la persistencia, como se detallará en la siguiente sección.

Python

\# 'checkpointer' es una instancia de un saver, como InMemorySaver.  
app \= workflow.compile(checkpointer=checkpointer)

LangGraph ofrece utilidades para visualizar la estructura del grafo compilado. Esto es extremadamente útil en sistemas complejos para verificar que los nodos y las aristas están conectados como se esperaba.9

Python

\# Requiere la instalación de 'pygraphviz' y 'graphviz'  
png\_data \= app.get\_graph().draw\_mermaid\_png()  
with open("supervisor\_graph.png", "wb") as f:  
    f.write(png\_data)

Esto generará una imagen del grafo, mostrando el nodo supervisor, los nodos de los agentes trabajadores y las aristas que los conectan, proporcionando una visión clara de la arquitectura del sistema.

## **VI. Garantizando la Continuidad: Persistencia de Estado y Memoria Conversacional**

Para que un chatbot sea verdaderamente útil, debe tener memoria. No puede tratar cada mensaje del usuario como una interacción aislada. La persistencia es el mecanismo que permite a la aplicación recordar el estado de la conversación a lo largo del tiempo, lo que es fundamental para el contexto, la personalización y la robustez.

### **El Rol Crítico de los Checkpointers**

Los Checkpointers son el sistema de persistencia incorporado de LangGraph. Cuando un grafo se compila con un checkpointer, el estado del grafo se guarda automáticamente en cada "super-paso" (generalmente, después de la ejecución de cada nodo).1 Esta capacidad habilita varias funcionalidades críticas:

* **Memoria Conversacional:** Permite que la conversación continúe a través de múltiples turnos. Cualquier mensaje de seguimiento se envía al mismo hilo de conversación, que conserva la memoria de las interacciones anteriores.1  
* **Intervención Humana (Human-in-the-loop):** Un humano puede inspeccionar el estado del grafo en cualquier punto, modificarlo si es necesario y luego reanudar la ejecución.1  
* **Tolerancia a Fallos:** Si un nodo falla, la ejecución se puede reiniciar desde el último checkpoint exitoso en lugar de empezar desde cero.1

Los conceptos clave del sistema de checkpointers son:

* **Thread (Hilo):** Un thread es una secuencia de estados guardados que representa una única conversación. Se identifica mediante un thread\_id único (por ejemplo, el ID de sesión de un usuario).1  
* **Checkpoint (Punto de Control):** Un checkpoint es una instantánea del estado completo del grafo en un momento específico dentro de un hilo.1

### **Implementación con Checkpointers**

La implementación de la persistencia es un proceso de dos pasos: instanciar un checkpointer y pasarlo al método compile().

Para el desarrollo y las pruebas, InMemorySaver es la opción más sencilla. Almacena todos los checkpoints en la memoria RAM, por lo que el estado se pierde cuando la aplicación se detiene.9

Python

from langgraph.checkpoint.memory import InMemorySaver  
from langgraph\_supervisor import create\_supervisor

\#... (definición de agentes y supervisor)

\# 1\. Instanciar el checkpointer  
checkpointer \= InMemorySaver()

\# 2\. Compilar el grafo con el checkpointer  
app \= workflow.compile(checkpointer=checkpointer)

Una vez compilado el grafo con un checkpointer, cada invocación debe incluir un thread\_id en el objeto de configuración. Esto le dice a LangGraph a qué conversación pertenece esta ejecución.1

Python

\# Cada usuario o sesión de chat debe tener un thread\_id único  
config \= {"configurable": {"thread\_id": "user\_session\_12345"}}

\# Invocar el grafo con la configuración  
app.invoke(  
    {"messages": \[{"role": "user", "content": "¿Cuál es el estado de mi pedido 12345?"}\]},  
    config=config  
)

\# En la siguiente interacción del mismo usuario  
app.invoke(  
    {"messages":},  
    config=config  \# Usando el mismo thread\_id  
)

### **Estrategias para Producción**

InMemorySaver no es adecuado para producción. Para entornos de producción, se deben utilizar checkpointers persistentes que almacenen los datos en una base de datos. LangGraph proporciona implementaciones listas para usar:

* langgraph.checkpoint.sqlite.SqliteSaver: Ideal para aplicaciones de un solo nodo o despliegues más pequeños, almacena los checkpoints en un archivo de base de datos SQLite.1  
* langgraph.checkpoint.postgres.PostgresSaver: La opción recomendada para aplicaciones escalables y distribuidas, utilizando una base de datos PostgreSQL como backend.1  
* Existen también implementaciones de la comunidad para otras bases de datos, como Couchbase.29

### **Gestión de Datos de Usuario entre Sesiones con MemoryStore**

Los checkpointers resuelven el problema de la memoria conversacional a corto plazo, es decir, el contexto *dentro de una única sesión de chat*. Sin embargo, una plataforma de e-commerce avanzada puede necesitar recordar información sobre un usuario *a través de múltiples sesiones*. Por ejemplo, recordar el nombre del usuario, sus preferencias de productos o su historial de compras, incluso si inicia una nueva conversación días después.

Aquí es donde se produce una distinción arquitectónica crucial. Los checkpointers, vinculados a un thread\_id, gestionan la memoria de la conversación. Para la memoria persistente del usuario, LangGraph proporciona un concepto complementario: MemoryStore.1

Un sistema de memoria de dos niveles es la arquitectura óptima para una experiencia de usuario de vanguardia:

* **Nivel 1 (Memoria Conversacional):** Gestionada por Checkpointers por thread\_id. Mantiene el contexto a corto plazo de la interacción actual.  
* **Nivel 2 (Memoria de Usuario a Largo Plazo):** Gestionada por MemoryStore por user\_id. Proporciona personalización y recuerda información clave a través de todas las conversaciones pasadas y futuras de un usuario.

El MemoryStore permite almacenar pares clave-valor arbitrarios en un namespace (espacio de nombres), que típicicamente se define por el ID del usuario. Dentro de los nodos de un agente, se puede acceder al store para guardar o recuperar esta información a largo plazo.1

Python

\# Concepto de uso dentro de un nodo de agente  
def some\_agent\_node(state, config):  
    user\_id \= config.get("configurable", {}).get("user\_id")  
    store \= config.get("store") \# El store se inyecta en la configuración  
      
    \# Recuperar preferencias del usuario  
    user\_preferences \= store.search(namespace=(user\_id, "preferences"))  
      
    \#... lógica del agente usando las preferencias...  
      
    \# Guardar una nueva preferencia  
    store.put(namespace=(user\_id, "preferences"), key="preferred\_category", value="electronics")  
      
    return {"messages": \[...\]}

La implementación de este sistema de memoria de dos niveles eleva al asistente de un simple chatbot conversacional a un verdadero asistente personal de compras.

## **VII. Diseño Avanzado para la Escalabilidad: Encapsulación de Agentes como Subgrafos**

A medida que el sistema crece en complejidad, gestionar a todos los agentes y su lógica dentro de un único grafo monolítico puede volverse insostenible. LangGraph aborda este desafío con el concepto de **subgrafos**, una poderosa herramienta de encapsulación que promueve la modularidad y la escalabilidad.

### **El Principio de Encapsulación**

Un subgrafo es un grafo de LangGraph completo que se utiliza como un único nodo dentro de otro grafo (el grafo padre).3 Esta técnica ofrece beneficios significativos para el diseño de sistemas complejos:

* **Modularidad:** Permite descomponer un sistema grande en componentes más pequeños y manejables. Cada agente o grupo de agentes puede ser su propio subgrafo.  
* **Reutilización:** Una lógica compleja, como un flujo de trabajo de RAG avanzado, puede construirse como un subgrafo y reutilizarse en diferentes partes de la aplicación o incluso en otros proyectos.  
* **Desarrollo Colaborativo:** Diferentes equipos pueden trabajar de forma independiente en distintos subgrafos. Mientras se respete la interfaz del subgrafo (su esquema de estado de entrada y salida), el grafo padre puede integrarlo sin necesidad de conocer los detalles de su implementación interna.3

### **Refactorización de un Agente Trabajador a un Subgrafo**

Consideremos el Agente de Consultas de Producto. Inicialmente, se implementó como un único objeto create\_react\_agent. Sin embargo, un flujo de trabajo de RAG de producción puede ser mucho más complejo, incluyendo pasos para reescribir la consulta, calificar la relevancia de los documentos recuperados y manejar casos en los que no se encuentra información.22 Todo este flujo de trabajo se puede encapsular en su propio

StateGraph.

Antes (Agente como objeto):  
El supervisor interactúa directamente con el objeto product\_agent creado por create\_react\_agent.  
**Después (Agente como subgrafo):**

1. Se crea un StateGraph completo para el flujo de trabajo de RAG de productos. Este grafo tiene sus propios nodos (p. ej., rewrite\_query, retrieve\_documents, grade\_documents) y su propio estado interno.  
2. Este grafo se compila en un objeto product\_subgraph.  
3. El grafo supervisor ahora trata a product\_subgraph como un único nodo.

### **Patrones de Comunicación entre el Grafo Padre y el Subgrafo**

Existen dos métodos principales para que el grafo padre y el subgrafo se comuniquen e intercambien estado 3:

1. **Claves de Estado Compartidas:** Este es el método más simple. Si el grafo padre y el subgrafo comparten claves en sus esquemas de estado (por ejemplo, ambos tienen una clave messages), el subgrafo compilado se puede añadir directamente como un nodo en el grafo padre. LangGraph pasará automáticamente los valores de las claves compartidas.  
   Python  
   \# El subgrafo y el grafo padre comparten 'MessagesState'  
   parent\_builder.add\_node("product\_agent\_node", product\_subgraph)

2. **Invocación dentro de un Nodo:** Este es el método más flexible y desacoplado, y el recomendado para una verdadera encapsulación. Se crea un nodo en el grafo padre cuya única función es invocar al subgrafo. Este nodo actúa como un adaptador:  
   * Recibe el estado del grafo padre.  
   * Transforma y prepara los datos de entrada en el formato que el subgrafo espera.  
   * Llama a subgraph.invoke() con los datos transformados.  
   * Recibe la respuesta del subgrafo.  
   * Transforma la respuesta de vuelta al formato del estado del grafo padre y la devuelve como una actualización.

Este patrón es ideal cuando el subgrafo tiene un estado interno complejo que no debe ser expuesto al grafo padre, manteniendo una separación limpia de responsabilidades.3Python  
def call\_product\_subgraph(state: ParentState) \-\> dict:  
    \# 1\. Transformar estado del padre al del subgrafo  
    subgraph\_input \= {"query": state\["messages"\]\[-1\].content}

    \# 2\. Invocar el subgrafo  
    subgraph\_output \= product\_subgraph.invoke(subgraph\_input)

    \# 3\. Transformar la salida del subgrafo al estado del padre  
    return {"messages": \[AIMessage(content=subgraph\_output\["answer"\])\]}

parent\_builder.add\_node("product\_agent\_node", call\_product\_subgraph)

El uso de subgrafos es una técnica avanzada que prepara la arquitectura para el crecimiento futuro, permitiendo que el sistema de IA evolucione de manera ordenada y mantenible.

## **VIII. Síntesis y Recomendaciones Estratégicas**

La implementación exitosa de un sistema multi-agente para e-commerce con LangGraph requiere no solo una comprensión técnica de la herramienta, sino también un enfoque estratégico en el diseño, la gestión y la evolución del sistema.

### **Buenas Prácticas Consolidadas**

* **Ingeniería de Prompts:** El prompt del supervisor es el mecanismo de control central. Debe ser tratado como código: versionado, probado rigurosamente y mantenido con cuidado. Pequeños cambios en el prompt pueden tener grandes impactos en el comportamiento del sistema.  
* **Diseño de Herramientas:** Las docstrings de las herramientas son el contrato de API para el LLM. Deben ser claras, descriptivas, inequívocas y detallar tanto la funcionalidad como los parámetros esperados.  
* **Gestión del Estado:** Utilice siempre un checkpointer de grado de producción en entornos reales. Establezca una clara distinción entre la memoria conversacional a corto plazo (gestionada por thread\_id) y la memoria de usuario a largo plazo (gestionada por user\_id y MemoryStore).  
* **Observabilidad:** Es fundamental utilizar una plataforma de trazabilidad como LangSmith. La capacidad de visualizar las trazas de ejecución, inspeccionar los estados intermedios y depurar las interacciones complejas entre agentes es indispensable para el desarrollo y mantenimiento de estos sistemas.32

### **Abordando Desafíos Potenciales**

* **Manejo de Errores:** Los nodos que interactúan con servicios externos (APIs, bases de datos) deben tener una lógica robusta para manejar fallos, como tiempos de espera, errores de red o respuestas inesperadas. Deben devolver actualizaciones de estado que informen al sistema del error de manera que el agente pueda intentar una acción diferente o escalar el problema.  
* **Latencia:** Los sistemas multi-agente pueden introducir latencia debido a las múltiples llamadas secuenciales a LLMs. Para mitigar la percepción del usuario, es crucial implementar streaming. LangGraph soporta el streaming de la salida final token por token, así como el streaming de los pasos intermedios, lo que permite mostrar al usuario el "razonamiento" del agente mientras trabaja, mejorando la experiencia de usuario.12  
* **"Chatter" de Agentes:** Se debe diseñar el grafo y los prompts para evitar bucles indeseados donde los agentes se pasan una tarea de un lado a otro sin llegar a una resolución. Esto a menudo indica un problema en la lógica de enrutamiento del supervisor o en las condiciones de finalización de los agentes trabajadores.

### **Una Hoja de Ruta por Fases para la Implementación**

Se recomienda un enfoque iterativo y por fases para construir el sistema, permitiendo la validación en cada etapa y reduciendo el riesgo.

1. **Fase 1 (Fundamentos):**  
   * **Objetivo:** Validar los conceptos básicos.  
   * **Acciones:** Construir un único agente trabajador (p. ej., el Agente de Gestión de Pedidos, que es más determinista). Implementar sus herramientas de API. Integrar un InMemorySaver para la persistencia y verificar que la memoria conversacional funciona en múltiples turnos.  
2. **Fase 2 (Orquestación Multi-Agente):**  
   * **Objetivo:** Implementar el enrutamiento básico.  
   * **Acciones:** Introducir el create\_supervisor. Añadir un segundo agente simple (p. ej., el Agente de Soporte General). Enfocarse en la ingeniería del prompt del supervisor para lograr un enrutamiento preciso entre los dos agentes.  
3. **Fase 3 (Agente RAG Avanzado):**  
   * **Objetivo:** Desarrollar la capacidad de recuperación de conocimiento.  
   * **Acciones:** Construir el Agente de Consultas de Producto. Esto implica configurar el pipeline de RAG (indexación de datos, almacén de vectores, herramienta de recuperación). Opcionalmente, encapsular este agente complejo como un subgrafo desde el principio para promover la modularidad.  
4. **Fase 4 (Endurecimiento para Producción):**  
   * **Objetivo:** Preparar el sistema para el despliegue.  
   * **Acciones:** Migrar el checkpointer a una solución de producción como PostgresSaver. Implementar un manejo de errores robusto en todas las herramientas. Integrar la memoria de usuario a largo plazo con MemoryStore. Configurar la monitorización y la observabilidad con LangSmith.

Siguiendo este plan estratégico y las directrices técnicas detalladas en este informe, una organización puede construir un asistente de e-commerce de próxima generación que no solo responda a las consultas de los clientes de manera eficiente, sino que también proporcione una base escalable y mantenible para la innovación futura en la inteligencia artificial conversacional.

#### **Obras citadas**

1. LangGraph persistence \- GitHub Pages, fecha de acceso: septiembre 5, 2025, [https://langchain-ai.github.io/langgraph/concepts/persistence/](https://langchain-ai.github.io/langgraph/concepts/persistence/)  
2. Mastering Persistence in LangGraph: Checkpoints, Threads, and Beyond | by Vinod Rane, fecha de acceso: septiembre 5, 2025, [https://medium.com/@vinodkrane/mastering-persistence-in-langgraph-checkpoints-threads-and-beyond-21e412aaed60](https://medium.com/@vinodkrane/mastering-persistence-in-langgraph-checkpoints-threads-and-beyond-21e412aaed60)  
3. Subgraphs \- GitHub Pages, fecha de acceso: septiembre 5, 2025, [https://langchain-ai.github.io/langgraph/concepts/subgraphs/](https://langchain-ai.github.io/langgraph/concepts/subgraphs/)  
4. Conversational Patterns in LangGraph using Subgraphs | by Vinodh S Iyer | Medium, fecha de acceso: septiembre 5, 2025, [https://medium.com/@vin4tech/conversational-patterns-in-langgraph-using-subgraphs-366d4dd27ebc](https://medium.com/@vin4tech/conversational-patterns-in-langgraph-using-subgraphs-366d4dd27ebc)  
5. Building an AI-Powered Agent with LLMs and LangGraph: A Retail Chatbot Example | by Venku Buragadda | Medium, fecha de acceso: septiembre 5, 2025, [https://medium.com/@venku.buragadda/building-an-agent-using-llm-491680706a90](https://medium.com/@venku.buragadda/building-an-agent-using-llm-491680706a90)  
6. LangGraph Tutorial: Building LLM Agents with LangChain's Agent Framework \- Zep, fecha de acceso: septiembre 5, 2025, [https://www.getzep.com/ai-agents/langgraph-tutorial/](https://www.getzep.com/ai-agents/langgraph-tutorial/)  
7. LangChain and Elasticsearch: Building LangGraph retrieval agent template, fecha de acceso: septiembre 5, 2025, [https://www.elastic.co/search-labs/blog/langchain-langgraph-retrieval-agent-template](https://www.elastic.co/search-labs/blog/langchain-langgraph-retrieval-agent-template)  
8. 1\. Build a basic chatbot \- GitHub Pages, fecha de acceso: septiembre 5, 2025, [https://langchain-ai.github.io/langgraph/tutorials/get-started/1-build-basic-chatbot/](https://langchain-ai.github.io/langgraph/tutorials/get-started/1-build-basic-chatbot/)  
9. Built with LangGraph\! \#17: Checkpoints | by Okan Yenigün | Aug ..., fecha de acceso: septiembre 5, 2025, [https://medium.com/towardsdev/built-with-langgraph-17-checkpoints-2d1d54e1464b](https://medium.com/towardsdev/built-with-langgraph-17-checkpoints-2d1d54e1464b)  
10. Building an Agentic RAG with LangGraph: A Step-by-Step Guide \- Medium, fecha de acceso: septiembre 5, 2025, [https://medium.com/@wendell\_89912/building-an-agentic-rag-with-langgraph-a-step-by-step-guide-009c5f0cce0a](https://medium.com/@wendell_89912/building-an-agentic-rag-with-langgraph-a-step-by-step-guide-009c5f0cce0a)  
11. Build a Retrieval Agent with LangGraph \- Exa, fecha de acceso: septiembre 5, 2025, [https://docs.exa.ai/examples/getting-started-with-rag-in-langgraph](https://docs.exa.ai/examples/getting-started-with-rag-in-langgraph)  
12. LangGraph \- LangChain, fecha de acceso: septiembre 5, 2025, [https://www.langchain.com/langgraph](https://www.langchain.com/langgraph)  
13. Multi-agent systems \- Overview, fecha de acceso: septiembre 5, 2025, [https://langchain-ai.github.io/langgraph/concepts/multi\_agent/\#multi-agent-architectures](https://langchain-ai.github.io/langgraph/concepts/multi_agent/#multi-agent-architectures)  
14. LangGraph Multi-Agent Systems \- Overview, fecha de acceso: septiembre 5, 2025, [https://langchain-ai.github.io/langgraph/concepts/multi\_agent/](https://langchain-ai.github.io/langgraph/concepts/multi_agent/)  
15. Build multi-agent systems \- GitHub Pages, fecha de acceso: septiembre 5, 2025, [https://langchain-ai.github.io/langgraph/how-tos/multi\_agent/](https://langchain-ai.github.io/langgraph/how-tos/multi_agent/)  
16. langchain-ai/langgraph-supervisor-py \- GitHub, fecha de acceso: septiembre 5, 2025, [https://github.com/langchain-ai/langgraph-supervisor-py](https://github.com/langchain-ai/langgraph-supervisor-py)  
17. Multi-agent supervisor \- GitHub Pages, fecha de acceso: septiembre 5, 2025, [https://langchain-ai.github.io/langgraph/tutorials/multi\_agent/agent\_supervisor/](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/)  
18. Building Multi-Agent Systems with LangGraph-Supervisor \- DEV ..., fecha de acceso: septiembre 5, 2025, [https://dev.to/sreeni5018/building-multi-agent-systems-with-langgraph-supervisor-138i](https://dev.to/sreeni5018/building-multi-agent-systems-with-langgraph-supervisor-138i)  
19. Langgraph Supervisior Agent Workflow Simplified | by Amanatullah | The Deep Hub, fecha de acceso: septiembre 5, 2025, [https://medium.com/thedeephub/langgraph-supervisior-agent-workflow-simplified-1aaf68b97072](https://medium.com/thedeephub/langgraph-supervisior-agent-workflow-simplified-1aaf68b97072)  
20. langgraph-supervisor \- PyPI, fecha de acceso: septiembre 5, 2025, [https://pypi.org/project/langgraph-supervisor/](https://pypi.org/project/langgraph-supervisor/)  
21. Understanding the LangGraph Multi-Agent Supervisor | by akansha khandelwal | Medium, fecha de acceso: septiembre 5, 2025, [https://medium.com/@khandelwal.akansha/understanding-the-langgraph-multi-agent-supervisor-00fa1be4341b](https://medium.com/@khandelwal.akansha/understanding-the-langgraph-multi-agent-supervisor-00fa1be4341b)  
22. Agentic RAG \- GitHub Pages, fecha de acceso: septiembre 5, 2025, [https://langchain-ai.github.io/langgraph/tutorials/rag/langgraph\_agentic\_rag/](https://langchain-ai.github.io/langgraph/tutorials/rag/langgraph_agentic_rag/)  
23. Building a RAG-powered E-commerce Platform (LangGraph \+ MongoDB \+ CopilotKit), fecha de acceso: septiembre 5, 2025, [https://www.copilotkit.ai/blog/building-a-rag-powered-e-commerce-platform-langgraph-mongodb-copilotkit](https://www.copilotkit.ai/blog/building-a-rag-powered-e-commerce-platform-langgraph-mongodb-copilotkit)  
24. langchain-ai/retrieval-agent-template \- GitHub, fecha de acceso: septiembre 5, 2025, [https://github.com/langchain-ai/retrieval-agent-template](https://github.com/langchain-ai/retrieval-agent-template)  
25. Build an Agent \- ️ LangChain, fecha de acceso: septiembre 5, 2025, [https://python.langchain.com/docs/tutorials/agents/](https://python.langchain.com/docs/tutorials/agents/)  
26. LangGraph Supervisor: A Library for Hierarchical Multi-Agent Systems, fecha de acceso: septiembre 5, 2025, [https://changelog.langchain.com/announcements/langgraph-supervisor-a-library-for-hierarchical-multi-agent-systems](https://changelog.langchain.com/announcements/langgraph-supervisor-a-library-for-hierarchical-multi-agent-systems)  
27. LangGraph Supervisor \- GitHub Pages, fecha de acceso: septiembre 5, 2025, [https://langchain-ai.github.io/langgraph/reference/supervisor/](https://langchain-ai.github.io/langgraph/reference/supervisor/)  
28. LangGraph Subgraphs: A Guide to Modular AI Agents Development \- DEV Community, fecha de acceso: septiembre 5, 2025, [https://dev.to/sreeni5018/langgraph-subgraphs-a-guide-to-modular-ai-agents-development-31ob](https://dev.to/sreeni5018/langgraph-subgraphs-a-guide-to-modular-ai-agents-development-31ob)  
29. Tutorial \- Persist LangGraph State with Couchbase Checkpointer, fecha de acceso: septiembre 5, 2025, [https://developer.couchbase.com/tutorial-langgraph-persistence-checkpoint/](https://developer.couchbase.com/tutorial-langgraph-persistence-checkpoint/)  
30. Use subgraphs \- Docs by LangChain, fecha de acceso: septiembre 5, 2025, [https://docs.langchain.com/oss/python/langgraph/use-subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)  
31. How to transform the input and output of a subgraph | LangChain OpenTutorial \- GitBook, fecha de acceso: septiembre 5, 2025, [https://langchain-opentutorial.gitbook.io/langchain-opentutorial/17-langgraph/01-core-features/14-langgraph-subgraph-transform-state](https://langchain-opentutorial.gitbook.io/langchain-opentutorial/17-langgraph/01-core-features/14-langgraph-subgraph-transform-state)  
32. langchain-ai/langgraph: Build resilient language agents as graphs. \- GitHub, fecha de acceso: septiembre 5, 2025, [https://github.com/langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)  
33. Build a Chatbot | 🦜️ LangChain, fecha de acceso: septiembre 5, 2025, [https://python.langchain.com/docs/tutorials/chatbot/](https://python.langchain.com/docs/tutorials/chatbot/)