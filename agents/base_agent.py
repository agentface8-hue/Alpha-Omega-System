from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config.settings import settings


class AgentClass(str, Enum):
    """Classification of agent roles in the governance hierarchy."""
    ANALYSIS = "analysis"           # Non-binding: generates signals
    ADVERSARIAL = "adversarial"     # Blocking-capable: challenges consensus
    RISK = "risk"                   # Veto-capable: can halt trades
    SYNTHESIS = "synthesis"         # Aggregates all outputs


class SignalDirection(str, Enum):
    """Standardized signal output from agents."""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    NEUTRAL = "NEUTRAL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"
    VETO = "VETO"                   # Only Risk agents can emit this


@dataclass
class ConfidenceBreakdown:
    """Decomposed confidence — no more opaque single numbers."""
    data_quality: float = 0.5       # 0-1: How reliable is the input data?
    signal_alignment: float = 0.5   # 0-1: Do signals agree across timeframes?
    regime_stability: float = 0.5   # 0-1: Is the macro regime stable?
    portfolio_fit: float = 0.5      # 0-1: Does this fit the portfolio?

    @property
    def composite(self) -> float:
        """Weighted composite confidence score."""
        weights = {
            'data_quality': 0.2,
            'signal_alignment': 0.35,
            'regime_stability': 0.25,
            'portfolio_fit': 0.2
        }
        return (
            self.data_quality * weights['data_quality'] +
            self.signal_alignment * weights['signal_alignment'] +
            self.regime_stability * weights['regime_stability'] +
            self.portfolio_fit * weights['portfolio_fit']
        )

    def to_dict(self) -> dict:
        return {
            'data_quality': round(self.data_quality, 3),
            'signal_alignment': round(self.signal_alignment, 3),
            'regime_stability': round(self.regime_stability, 3),
            'portfolio_fit': round(self.portfolio_fit, 3),
            'composite': round(self.composite, 3)
        }


@dataclass
class AgentVote:
    """Structured output from every agent in the council."""
    agent_name: str
    agent_class: str                        # AgentClass value
    signal: str                             # SignalDirection value
    confidence: float                       # 0-1 composite
    confidence_breakdown: Optional[ConfidenceBreakdown] = None
    rationale: str = ""                     # Core reasoning
    dissent: str = ""                       # What the agent disagrees with
    veto: bool = False                      # Only Risk agents can set True
    veto_reason: str = ""                   # Required if veto=True
    failure_scenarios: List[str] = field(default_factory=list)  # Bear case
    position_cap: Optional[float] = None    # Max allocation (Risk agents)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        result = {
            'agent_name': self.agent_name,
            'agent_class': self.agent_class,
            'signal': self.signal,
            'confidence': round(self.confidence, 3),
            'rationale': self.rationale,
            'dissent': self.dissent,
            'veto': self.veto,
            'veto_reason': self.veto_reason,
            'failure_scenarios': self.failure_scenarios,
        }
        if self.confidence_breakdown:
            result['confidence_breakdown'] = self.confidence_breakdown.to_dict()
        if self.position_cap is not None:
            result['position_cap'] = self.position_cap
        if self.metadata:
            result['metadata'] = self.metadata
        return result


class BaseAgent(ABC):
    """
    Abstract base class for all Alpha-Omega agents.
    V2: Structured outputs via AgentVote, agent classification, governance support.
    """

    AGENT_CLASS: AgentClass = AgentClass.ANALYSIS  # Override in subclasses

    def __init__(
        self,
        name: str,
        role: str,
        goal: str,
        llm_backend: str = "google",
        model: str = settings.DEFAULT_LLM_MODEL,
        tools: List[Any] = None
    ):
        self.name = name
        self.role = role
        self.goal = goal
        self.llm_backend = llm_backend
        self.model_name = model
        self.tools = tools or []
        self.llm = self._initialize_llm()
        self.memory: List[BaseMessage] = []

    @property
    def agent_class(self) -> str:
        return self.AGENT_CLASS.value

    @property
    def can_veto(self) -> bool:
        return self.AGENT_CLASS == AgentClass.RISK

    def _initialize_llm(self):
        """Initialize the LLM based on backend choice."""
        if self.llm_backend == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=self.model_name,
                temperature=0.7,
                base_url=settings.OLLAMA_BASE_URL,
            )
        elif self.llm_backend == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=self.model_name,
                temperature=0.7,
                api_key=settings.OPENAI_API_KEY
            )
        elif self.llm_backend == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=self.model_name,
                temperature=0.7,
                api_key=settings.ANTHROPIC_API_KEY
            )
        elif self.llm_backend == "google":
            return ChatGoogleGenerativeAI(
                model=self.model_name,
                temperature=0.7,
                google_api_key=settings.GOOGLE_API_KEY
            )
        else:
            raise ValueError(f"Unsupported LLM backend: {self.llm_backend}")

    def add_to_memory(self, message: BaseMessage):
        self.memory.append(message)

    def clear_memory(self):
        self.memory = []

    @abstractmethod
    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Legacy execution — returns free text. Override for backward compat."""
        pass

    def vote(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentVote:
        """
        V2 structured execution — returns an AgentVote.
        Default implementation wraps execute() output.
        Subclasses should override for proper structured output.
        """
        raw_output = self.execute(task, context)
        return AgentVote(
            agent_name=self.name,
            agent_class=self.agent_class,
            signal=SignalDirection.NEUTRAL.value,
            confidence=0.5,
            rationale=raw_output,
        )

    def _build_system_prompt(self) -> str:
        return f"""
        You are {self.name}, the {self.role}.
        Your goal is: {self.goal}.
        
        Operate as a top-tier expert in your field. 
        Provide well-reasoned, data-backed analysis.
        """

    def query_llm(self, prompt: str, system_prompt: Optional[str] = None, timeout: float = 35.0) -> str:
        sys_prompt = system_prompt or self._build_system_prompt()
        messages = [SystemMessage(content=sys_prompt)] + self.memory + [HumanMessage(content=prompt)]
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(self.llm.invoke, messages)
            try:
                response = fut.result(timeout=timeout)
            except FutTimeout:
                return f"{self.name}: analysis timed out — using council consensus."
            except Exception as e:
                return f"{self.name}: unavailable ({str(e)[:100]})."
        return response.content
