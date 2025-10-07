from fasthtml.common import *
from agent_graph import graph
import uuid

app, rt = fast_app()

# Хранилище сессий (в production используйте Redis или БД)
sessions = {}

def get_session(session_id: str):
    if session_id not in sessions:
        sessions[session_id] = {"thread_id": str(uuid.uuid4())}
    return sessions[session_id]

# Главная страница
@rt('/')
def get():
    return Div(
        H1("🤖 ИИ-помощник с Human-in-the-Loop"),
        Div(
            P("Попробуйте запросы типа: ", 
              Span("'перевод денег'", style="font-weight: bold; color: red;"), 
              ", ", 
              Span("'купить акции'", style="font-weight: bold; color: red;"),
              " чтобы увидеть HITL в действии"),
            style="background: #f0f8ff; padding: 10px; border-radius: 5px; margin-bottom: 20px;"
        ),
        # Контейнер для истории сообщений
        Div(
            Div(
                Div("Ассистент: Добро пожаловать! Я ваш ИИ-помощник. Некоторые действия требуют подтверждения человека.", 
                    style="color: green; margin: 5px 0;"),
                id="chat-messages"
            ),
            style="height: 400px; overflow-y: auto; border: 1px solid #ccc; padding: 10px; background: white; border-radius: 5px;"
        ),
        # Форма ввода сообщения
        Form(
            Div(
                Input(
                    type="text", 
                    name="message", 
                    placeholder="Введите ваш запрос...", 
                    required=True,
                    style="flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 4px;"
                ),
                Button("📨 Отправить", 
                       type="submit",
                       style="margin-left: 10px; padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;"
                ),
                style="display: flex;"
            ),
            hx_post="/chat",
            hx_target="#chat-messages",
            hx_swap="beforeend",
            style="margin-top: 20px;"
        ),
        # Скрытая форма для подтверждения действий
        Div(
            Form(
                Div(
                    Span(id="pending-action", style="font-weight: bold; color: red;"),
                    style="margin-bottom: 10px;"
                ),
                Div(
                    Button("✅ Подтвердить", 
                           type="submit", 
                           name="feedback", 
                           value="approve",
                           style="padding: 8px 15px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; margin-right: 10px;"
                    ),
                    Button("❌ Отклонить", 
                           type="submit", 
                           name="feedback", 
                           value="reject",
                           style="padding: 8px 15px; background: #dc3545; color: white; border: none; border-radius: 4px; cursor: pointer;"
                    ),
                ),
                hx_post="/human-feedback",
                hx_target="#chat-messages",
                hx_swap="beforeend",
                id="approval-form",
                style="display: none; background: #fff3cd; padding: 15px; border: 1px solid #ffeaa7; border-radius: 5px; margin-top: 10px;"
            ),
            id="approval-container"
        ),
        Script("""
            function scrollToBottom() {
                var container = document.getElementById('chat-messages').parentElement;
                container.scrollTop = container.scrollHeight;
            }
            
            // Автопрокрутка после обновления HTMX
            document.body.addEventListener('htmx:afterSwap', function() {
                setTimeout(scrollToBottom, 100);
            });
            
            // Показать/скрыть форму подтверждения
            function toggleApprovalForm(show, actionText) {
                var form = document.getElementById('approval-form');
                var actionSpan = document.getElementById('pending-action');
                if (show) {
                    actionSpan.textContent = 'Требуется подтверждение для: ' + actionText;
                    form.style.display = 'block';
                } else {
                    form.style.display = 'none';
                }
            }
        """),
        style="max-width: 800px; margin: 0 auto; padding: 20px; background: #f8f9fa; min-height: 100vh;"
    )

# Обработчик чат-запросов
@rt('/chat')
def post(request, message: str):
    session_id = request.cookies.get('session_id', str(uuid.uuid4()))
    session = get_session(session_id)
    
    config = {"configurable": {"thread_id": session['thread_id']}}
    user_message = {"role": "user", "content": message}
    
    # Выполняем граф
    events = graph.invoke({"messages": [user_message]}, config)
    
    # Формируем ответ
    response_elements = []
    
    # Добавляем сообщение пользователя
    response_elements.append(
        Div(
            Div(f"👤 Вы: {message}", style="text-align: right; color: blue; margin: 10px 0; background: #e3f2fd; padding: 8px 12px; border-radius: 15px 15px 0 15px;"),
            style="display: flex; justify-content: flex-end;"
        )
    )
    
    # Добавляем ответ ассистента
    assistant_messages = [e for e in events['messages'] if e['role'] == 'assistant']
    if assistant_messages:
        last_assistant_msg = assistant_messages[-1]['content']
        response_elements.append(
            Div(
                Div(f"🤖 Ассистент: {last_assistant_msg}", style="text-align: left; color: green; margin: 10px 0; background: #f1f8e9; padding: 8px 12px; border-radius: 15px 15px 15px 0;"),
                style="display: flex; justify-content: flex-start;"
            )
        )
    
    # Если требуется подтверждение человека, добавляем скрипт для показа формы
    if events.get('needs_human_approval') and events.get('pending_action'):
        response_elements.append(
            Script(f"""
                toggleApprovalForm(true, '{events['pending_action']}');
            """)
        )
    else:
        response_elements.append(
            Script("toggleApprovalForm(false, '');")
        )
    
    # Устанавливаем cookie для сессии
    response = Div(*response_elements)
    if 'session_id' not in request.cookies:
        response.headers['Set-Cookie'] = f'session_id={session_id}; Path=/; HttpOnly'
    
    return response

# Обработчик обратной связи от человека
@rt('/human-feedback')
def post_human_feedback(request, feedback: str):
    session_id = request.cookies.get('session_id')
    if not session_id:
        return Div("Ошибка: сессия не найдена")
    
    session = get_session(session_id)
    config = {"configurable": {"thread_id": session['thread_id']}}
    
    # Преобразуем feedback в human_feedback
    human_feedback = "да" if feedback == "approve" else "нет"
    
    # Продолжаем выполнение графа с обратной связью
    events = graph.invoke({
        "human_feedback": human_feedback
    }, config)
    
    # Формируем ответ
    response_elements = []
    
    # Добавляем решение человека
    decision_text = "✅ Человек подтвердил действие" if feedback == "approve" else "❌ Человек отклонил действие"
    response_elements.append(
        Div(
            Div(f"👨‍💼 {decision_text}", style="text-align: center; color: orange; margin: 10px 0; background: #fff3cd; padding: 8px 12px; border-radius: 15px; border: 1px solid #ffeaa7;"),
            style="display: flex; justify-content: center;"
        )
    )
    
    # Добавляем ответ ассистента
    assistant_messages = [e for e in events['messages'] if e['role'] == 'assistant']
    if assistant_messages:
        last_assistant_msg = assistant_messages[-1]['content']
        response_elements.append(
            Div(
                Div(f"🤖 Ассистент: {last_assistant_msg}", style="text-align: left; color: green; margin: 10px 0; background: #f1f8e9; padding: 8px 12px; border-radius: 15px 15px 15px 0;"),
                style="display: flex; justify-content: flex-start;"
            )
        )
    
    # Скрываем форму подтверждения
    response_elements.append(
        Script("toggleApprovalForm(false, '');")
    )
    
    return Div(*response_elements)

if __name__ == "__main__":
    serve(port=5001)
