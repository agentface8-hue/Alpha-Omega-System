from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor
from agents.historian import HistorianAgent
from agents.newsroom import NewsroomAgent
from agents.macro_strategist import MacroStrategistAgent
from agents.contrarian import ContrarianAgent
from agents.executioner import ExecutionerAgent
from agents.regime_detector import RegimeDetectorAgent
from agents.bear_case_advocate import BearCaseAdvocateAgent
from agents.risk_officer import RiskOfficerAgent
from agents.portfolio_architect import PortfolioArchitectAgent
from agents.base_agent import AgentVote, SignalDirection, AgentClass
from core.decision_matrix import DecisionMatrix, build_default_scenarios
from core.decision_ledger import record_decision
from core.timeout_utils import run_with_timeout
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config.settings import settings


class Orchestrator:
    """
    The Lead Coordinator for Alpha-Omega.
    Manages the "Council of Experts" workflow: Ingestion -> Debate -> Synthesis -> Action.
    """
    def __init__(self):
        self.historian = HistorianAgent(llm_backend="google")
        self.newsroom = NewsroomAgent(llm_backend="google")
        self.macro = MacroStrategistAgent(llm_backend="google")
        self.contrarian = ContrarianAgent(llm_backend="google")
        self.executioner = ExecutionerAgent(llm_backend="google")
        # Council agents (V2 governance)
        self.regime_detector = RegimeDetectorAgent(llm_backend="google")
        self.bear_case_advocate = BearCaseAdvocateAgent(llm_backend="google")
        self.risk_officer = RiskOfficerAgent(llm_backend="google")
        self.portfolio_architect = PortfolioArchitectAgent(llm_backend="google")

        # Coordinator LLM for synthesis
        self.coordinator_llm = ChatGoogleGenerativeAI(
            model=settings.FAST_LLM_MODEL,
            temperature=0.3,
            google_api_key=settings.GOOGLE_API_KEY
        )

    def _run_timed(self, fn, timeout: float = 40.0, fallback: str = "Unavailable"):
        return run_with_timeout(fn, timeout_s=timeout, fallback=fallback)

    def _build_executioner_decision(
        self,
        symbol: str,
        recommendation: str,
        position_size_pct: float,
        vetoed: bool,
        veto_reason: str,
        consensus_view: str,
        confidence_score: float,
        agent_votes: Dict[str, AgentVote],
    ) -> str:
        """Deterministic Executioner verdict from council output — always instant."""
        conf_pct = round(confidence_score * 100)
        rd = agent_votes.get("Regime Detector")
        regime = (rd.metadata.get("detected_regime") if rd and rd.metadata else "Unknown")
        thesis = (consensus_view or "No consensus")[:220]
        if vetoed:
            return (
                f"HALT — Council VETO on {symbol}. "
                f"{veto_reason or 'Risk limits breached.'} Do not enter."
            )
        if recommendation == "BUY":
            return (
                f"BUY {symbol} — Council approved ({conf_pct}% confidence, {regime}). "
                f"Allocate up to {position_size_pct:.1f}% of portfolio. "
                f"Set stop per Risk Officer tiers. Thesis: {thesis}"
            )
        if recommendation == "SELL":
            return f"SELL / REDUCE {symbol} — Council bearish ({conf_pct}% confidence, {regime})."
        return (
            f"HOLD {symbol} — Confidence {conf_pct}% or mixed council signals. "
            f"Monitor for decisive breakout. {thesis}"
        )

    def synthesize_reports(self, reports: Dict[str, str], symbol: str) -> Dict[str, Any]:
        """
        Synthesizes reports from Historian, Newsroom, and Macro into a Consensus View.
        Also calculates a preliminary confidence score.
        """
        prompt = f"""
        You are the Head of Research for a hedge fund.
        Synthesize the following reports for {symbol} into a single "Consensus View":
        
        --- The Historian (Technical) ---
        {reports['historian']}
        
        --- The Newsroom (Sentiment) ---
        {reports['newsroom']}
        
        --- The Macro-Strategist (Global) ---
        {reports['macro']}
        
        Output Requirements:
        1. A concise "Consensus View" paragraph summary.
        2. A numeric "Confidence Score" (0.0 to 1.0) based on the alignment of signals.
        
        Format:
        Consensus View: [Summary]
        Confidence Score: [0.0-1.0]
        """
        
        response = self.coordinator_llm.invoke([HumanMessage(content=prompt)]).content
        
        # Simple parsing (robust parsing would be needed in prod)
        lines = response.split('\n')
        consensus_view = "Analysis unavailable."
        confidence_score = 0.5
        
        for line in lines:
            if "Consensus View:" in line:
                consensus_view = line.replace("Consensus View:", "").strip()
            if "Confidence Score:" in line:
                try:
                    confidence_score = float(line.replace("Confidence Score:", "").strip())
                except ValueError:
                    pass
                    
        return {
            "consensus_view": consensus_view,
            "confidence_score": confidence_score,
            "full_synthesis": response
        }

    def run_cycle(self, symbol: str) -> Dict[str, Any]:
        """
        Runs the full Alpha-Omega trading cycle.
        Returns the full context including decision, analysis, and confidence score.
        """
        print(f"--- Starting Alpha-Omega Cycle for {symbol} ---")
        
        # 1. Ingestion & Individual Analysis
        print("1. Gathering Intelligence from Agents...")
        reports = {}
        reports['historian'] = self.historian.execute("Analyze price action.", {"symbol": symbol})
        reports['newsroom'] = self.newsroom.execute("Analyze sentiment.", {"symbol": symbol})
        reports['macro'] = self.macro.execute("Analyze macro regime impact.", {"symbol": symbol})
        
        # 2. Initial Synthesis
        print("2. Synthesizing Preliminary Consensus...")
        synthesis = self.synthesize_reports(reports, symbol)
        
        # 3. The Debate (Contrarian Challenge)
        print("3. The Contrarian is challenging the view...")
        challenge = self.contrarian.execute(
            "Challenge this consensus.", 
            {"symbol": symbol, "consensus_view": synthesis['consensus_view']}
        )
        
        # 4. Final Decision (Executioner)
        print("4. The Executioner is deciding...")
        
        final_context = {
            "symbol": symbol,
            "analysis_summary": f"""
            Consensus View: {synthesis['consensus_view']}
            Confidence Score: {synthesis['confidence_score']}
            Contrarian Challenge: {challenge}
            """,
            "confidence_score": synthesis['confidence_score'],
            "consensus_view": synthesis['consensus_view'],
            "contrarian_challenge": challenge,
            "reports": reports
        }
        
        decision = self.executioner.execute("Make final trade decision.", final_context)
        final_context["decision"] = decision
        
        print("--- Cycle Complete ---\n")
        return final_context

    def _aggregate_signal(self, agent_votes: Dict[str, AgentVote]) -> str:
        """Map council votes to a single signal (BUY, STRONG_BUY, NEUTRAL, SELL, STRONG_SELL) for scenarios."""
        signal_scores = {
            SignalDirection.STRONG_BUY.value: 2.0,
            SignalDirection.BUY.value: 1.0,
            SignalDirection.NEUTRAL.value: 0.0,
            SignalDirection.SELL.value: -1.0,
            SignalDirection.STRONG_SELL.value: -2.0,
            SignalDirection.VETO.value: -2.0,
        }
        total_weight = 0.0
        weighted_sum = 0.0
        for vote in agent_votes.values():
            score = signal_scores.get(vote.signal, 0.0)
            w = vote.confidence
            weighted_sum += score * w
            total_weight += w
        if total_weight <= 0:
            return SignalDirection.NEUTRAL.value
        avg = weighted_sum / total_weight
        if avg >= 1.0:
            return SignalDirection.STRONG_BUY.value
        if avg >= 0.3:
            return SignalDirection.BUY.value
        if avg <= -1.0:
            return SignalDirection.STRONG_SELL.value
        if avg <= -0.3:
            return SignalDirection.SELL.value
        return SignalDirection.NEUTRAL.value

    def run_cycle_v2(self, symbol: str, portfolio: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        V2 cycle: Ingestion -> Synthesis -> Council (votes) -> Veto/aggregate -> DecisionMatrix -> Ledger.
        Returns full context including agent_votes, decision_matrix, and decision_id.
        """
        portfolio = portfolio or {}
        print(f"--- Starting Alpha-Omega Cycle V2 for {symbol} ---")

        # Phase A — Ingestion (parallel for speed)
        print("1. Gathering Intelligence from Agents...")
        reports: Dict[str, str] = {}
        ctx_base = {"symbol": symbol}

        def _hist():
            return self.historian.execute("Analyze price action.", ctx_base)
        def _news():
            return self.newsroom.execute("Analyze sentiment.", ctx_base)
        def _macro():
            return self.macro.execute("Analyze macro regime impact.", ctx_base)

        with ThreadPoolExecutor(max_workers=3) as pool:
            f_h = pool.submit(_hist)
            f_n = pool.submit(_news)
            f_m = pool.submit(_macro)
            for key, fut in [("historian", f_h), ("newsroom", f_n), ("macro", f_m)]:
                try:
                    reports[key] = fut.result(timeout=45)
                except Exception as e:
                    reports[key] = f"{key} unavailable: {str(e)[:120]}"

        print("2. Synthesizing Preliminary Consensus...")
        synthesis = self._run_timed(
            lambda: self.synthesize_reports(reports, symbol),
            35,
            {"consensus_view": "Synthesis unavailable.", "confidence_score": 0.5, "full_synthesis": ""},
        )
        if isinstance(synthesis, str):
            synthesis = {"consensus_view": synthesis, "confidence_score": 0.5, "full_synthesis": synthesis}
        consensus_view = synthesis["consensus_view"]
        confidence_score = synthesis["confidence_score"]

        # Macro data for Regime Detector
        macro_data = self.macro.fetch_macro_data() if hasattr(self.macro, "fetch_macro_data") else {}

        # Phase B — Council: collect votes (RD, BCA first; then RO with RD+BCA; then PA)
        print("3. Council voting (Regime Detector, Bear Case Advocate, Risk Officer, Portfolio Architect)...")
        task = "Evaluate this trade proposal."
        agent_votes: Dict[str, AgentVote] = {}

        def _fallback_vote(name: str, note: str) -> AgentVote:
            return AgentVote(
                agent_name=name,
                agent_class=AgentClass.ANALYSIS.value,
                signal=SignalDirection.NEUTRAL.value,
                confidence=0.5,
                rationale=note,
            )

        ctx_rd = {"symbol": symbol, "macro_data": macro_data, "reports": reports}
        ctx_bca = {"symbol": symbol, "consensus_view": consensus_view, "reports": reports}

        with ThreadPoolExecutor(max_workers=2) as pool:
            f_rd = pool.submit(self.regime_detector.vote, task, ctx_rd)
            f_bca = pool.submit(self.bear_case_advocate.vote, task, ctx_bca)
            try:
                agent_votes["Regime Detector"] = f_rd.result(timeout=35)
            except Exception as e:
                agent_votes["Regime Detector"] = _fallback_vote("Regime Detector", str(e)[:120])
            try:
                agent_votes["Bear Case Advocate"] = f_bca.result(timeout=35)
            except Exception as e:
                agent_votes["Bear Case Advocate"] = _fallback_vote("Bear Case Advocate", str(e)[:120])

        ctx_ro = {
            "symbol": symbol,
            "consensus_view": consensus_view,
            "confidence_score": confidence_score,
            "agent_votes": agent_votes,
        }
        ctx_pa = {
            "symbol": symbol,
            "consensus_view": consensus_view,
            "confidence_score": confidence_score,
            "portfolio": portfolio,
        }
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_ro = pool.submit(self.risk_officer.vote, task, ctx_ro)
            f_pa = pool.submit(self.portfolio_architect.vote, task, ctx_pa)
            try:
                agent_votes["The Risk Officer"] = f_ro.result(timeout=35)
            except Exception as e:
                agent_votes["The Risk Officer"] = _fallback_vote("The Risk Officer", str(e)[:120])
            try:
                agent_votes["Portfolio Architect"] = f_pa.result(timeout=35)
            except Exception as e:
                agent_votes["Portfolio Architect"] = _fallback_vote("Portfolio Architect", str(e)[:120])

        # Phase C — Veto and recommendation
        vetoed = any(v.veto for v in agent_votes.values())
        veto_reason = ""
        for v in agent_votes.values():
            if v.veto and v.veto_reason:
                veto_reason = v.veto_reason
                break

        if vetoed:
            recommendation = "VETO"
            position_size_pct = 0.0
            aggregate_signal = SignalDirection.NEUTRAL.value
        else:
            aggregate_signal = self._aggregate_signal(agent_votes)
            caps = []
            for v in agent_votes.values():
                if v.position_cap is not None:
                    caps.append(v.position_cap)
            position_size_pct = min(caps) if caps else 5.0
            if aggregate_signal in (SignalDirection.STRONG_BUY.value, SignalDirection.BUY.value):
                recommendation = "BUY"
            elif aggregate_signal in (SignalDirection.STRONG_SELL.value, SignalDirection.SELL.value):
                recommendation = "SELL"
            else:
                recommendation = "HOLD"

        # Confidence and breakdown for ledger (prefer Risk Officer's)
        confidence_breakdown = {}
        risk_assessment: Dict[str, Any] = {}
        for v in agent_votes.values():
            if v.confidence_breakdown:
                confidence_breakdown = v.confidence_breakdown.to_dict()
                break
        ro_vote = agent_votes.get("The Risk Officer")
        if ro_vote and ro_vote.metadata:
            risk_assessment = dict(ro_vote.metadata)

        # Phase D — DecisionMatrix and Ledger
        scenarios = build_default_scenarios(confidence_score, aggregate_signal)
        decision_matrix = DecisionMatrix(
            symbol=symbol,
            scenarios=scenarios,
            recommendation=recommendation,
            position_size_pct=position_size_pct,
        )
        agent_votes_serialized = {name: v.to_dict() for name, v in agent_votes.items()}
        # Persist regime at decision time (ledger is source of truth; attribution reads decision.regime)
        regime = "UNKNOWN"
        rd_vote = agent_votes.get("Regime Detector")
        if rd_vote and getattr(rd_vote, "metadata", None):
            regime = rd_vote.metadata.get("detected_regime", "UNKNOWN")
        decision_data = {
            "symbol": symbol,
            "recommendation": recommendation,
            "confidence": confidence_score,
            "confidence_breakdown": confidence_breakdown,
            "decision_matrix": decision_matrix.to_dict(),
            "agent_votes": agent_votes_serialized,
            "risk_assessment": risk_assessment,
            "consensus_view": consensus_view,
            "position_size_pct": position_size_pct,
            "vetoed": vetoed,
            "veto_reason": veto_reason,
            "regime": regime,
        }
        decision_id = record_decision(decision_data)
        executioner_decision = self._build_executioner_decision(
            symbol, recommendation, position_size_pct, vetoed, veto_reason,
            consensus_view, confidence_score, agent_votes,
        )
        print(f"4. Executioner: {executioner_decision[:80]}...")
        print(f"5. Decision recorded (id={decision_id}). Recommendation: {recommendation}.")
        print("--- Cycle V2 Complete ---\n")

        return {
            "symbol": symbol,
            "consensus_view": consensus_view,
            "confidence_score": confidence_score,
            "reports": reports,
            "agent_votes": agent_votes,
            "agent_votes_serialized": agent_votes_serialized,
            "vetoed": vetoed,
            "veto_reason": veto_reason,
            "recommendation": recommendation,
            "position_size_pct": position_size_pct,
            "executioner_decision": executioner_decision,
            "decision_matrix": decision_matrix,
            "decision_id": decision_id,
            "decision_data": decision_data,
        }
