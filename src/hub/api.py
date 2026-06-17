from ninja import Router
from .models import CommerceAgent, Product
from django.shortcuts import get_object_or_404
from users.jwt import JWTBearer
import uuid

router = Router(auth=[JWTBearer()])

@router.post("/agents/")
def register_agent(request, name: str, description: str, fetch_address: str, wallet_address: str):
    agent = CommerceAgent.objects.create(
        name=name,
        description=description,
        fetch_address=fetch_address,
        wallet_address=wallet_address,
        owner=request.user,
        status="ACTIVE"
    )
    return {"id": agent.id, "name": agent.name, "status": agent.status}

@router.get("/agents/")
def list_agents(request):
    agents = CommerceAgent.objects.filter(owner=request.user)
    return [{"id": a.id, "name": a.name, "status": a.status, "fetch_address": a.fetch_address} for a in agents]

@router.post("/fetch-ai/messages/")
def receive_fetch_ai_message(request, sender: str, target_agent: str, payload: dict):
    # Simulate Fetch.ai Agent Chat Protocol
    agent = get_object_or_404(CommerceAgent, fetch_address=target_agent)
    return {"status": "Message received", "agent": agent.name, "response": f"Acknowledged by {agent.name}"}

@router.post("/metta/query/")
def metta_knowledge_query(request, query: str):
    # Simulate MeTTa decentralized knowledge graph query
    # E.g., matching item based on graph reasoning
    products = Product.objects.all()
    matches = [{"id": p.id, "name": p.name} for p in products if p.name.lower() in query.lower() or query.lower() in p.name.lower()]
    return {"query": query, "matches": matches, "reasoning": "Graph match simulated via MeTTa semantics"}

@router.get("/dashboard/")
def agent_dashboard(request):
    agents = CommerceAgent.objects.all()
    active_count = agents.filter(status="ACTIVE").count()
    return {
        "total_agents": agents.count(),
        "active_agents": active_count,
        "health": "OK" if active_count > 0 else "WARNING"
    }
