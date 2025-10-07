from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Optional
from langgraph.checkpoint.memory import MemorySaver
import asyncio

# Расширенное состояние агента
class AgentState(TypedDict):
    messages: Annotated[list, lambda a, b: a + b]  # История диалога
    needs_human_approval: bool  # Требуется ли подтверждение человека
    pending_action: Optional[str]  # Ожидающее действие для подтверждения
    human_feedback: Optional[str]  # Обратная связь от человека

# Функция для принятия решений агентом
def decision_maker(state: AgentState):
    last_message = state['messages'][-1]['content'] if state['messages'] else ""
    
    # Пример логики: запрашиваем подтверждение для определенных действий
    sensitive_actions = ["перевод денег", "удалить", "купить", "оплатить"]
    
    for action in sensitive_actions:
        if action in last_message.lower():
            return {
                "messages": [{
                    "role": "assistant", 
                    "content": f"Обнаружено действие: '{action}'. Требуется подтверждение человека для выполнения."
                }],
                "needs_human_approval": True,
                "pending_action": action,
                "human_feedback": None
            }
    
    # Обычный ответ без подтверждения
    return {
        "messages": [{
            "role": "assistant", 
            "content": f"Обработал ваш запрос: '{last_message}'. Это безопасное действие, выполняю автоматически."
        }],
        "needs_human_approval": False,
        "pending_action": None,
        "human_feedback": None
    }

# Функция для обработки подтверждения человека
def human_approval_handler(state: AgentState):
    if state.get('human_feedback'):
        feedback = state['human_feedback']
        pending_action = state.get('pending_action', 'действие')
        
        if feedback.lower() in ['да', 'confirm', 'approve', 'yes']:
            return {
                "messages": [{
                    "role": "assistant", 
                    "content": f"✅ Действие '{pending_action}' подтверждено человеком. Выполняю..."
                }],
                "needs_human_approval": False,
                "pending_action": None,
                "human_feedback": None
            }
        else:
            return {
                "messages": [{
                    "role": "assistant", 
                    "content": f"❌ Действие '{pending_action}' отклонено человеком. Отменяю операцию."
                }],
                "needs_human_approval": False,
                "pending_action": None,
                "human_feedback": None
            }
    
    return state

# Создаем и компилируем граф с HITL
def create_agent_graph():
    workflow = StateGraph(AgentState)
    
    # Добавляем ноды в граф
    workflow.add_node("decision_maker", decision_maker)
    workflow.add_node("human_approval", human_approval_handler)
    
    # Определяем точки входа
    workflow.set_entry_point("decision_maker")
    
    # Условные переходы
    def should_wait_for_human(state: AgentState):
        if state.get('needs_human_approval') and not state.get('human_feedback'):
            return "human_approval"
        return END
    
    workflow.add_conditional_edges(
        "decision_maker",
        should_wait_for_human
    )
    
    workflow.add_edge("human_approval", END)
    
    # Компилируем граф с памятью
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)

# Глобальная инициализация графа
graph = create_agent_graph()
