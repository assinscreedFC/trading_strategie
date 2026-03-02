# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# MODULE : telegram_notifier.py
# RÔLE  : Notifications Telegram centralisées pour TOUTES stratégies
# ══════════════════════════════════════════════════════════════
#
# ARCHITECTURE DE REFACTORING :
# → Ce module est le SEUL point d'envoi Telegram.
# → Aucune stratégie ne doit implémenter son propre envoi.
# → Supporte : texte, alertes trade, rapports, erreurs.
#
# CHOIX TECHNIQUES :
# 1. Utilise l'API Telegram directe (requests) plutôt que
#    python-telegram-bot pour éviter l'overhead async
# 2. Rate limiting intégré pour respecter les limites Telegram
#    (30 messages/sec par bot, 20 messages/min par groupe)
# 3. Mode silencieux si bot_token est vide (pas de crash)
#
# CONFIGURATION :
#   Les tokens sont lus depuis les variables d'environnement
#   OU passés directement au constructeur.
#   → TELEGRAM_BOT_TOKEN
#   → TELEGRAM_CHAT_ID
#
# USAGE :
#   from utils.telegram_notifier import TelegramNotifier
#   notifier = TelegramNotifier()  # lit depuis env
#   notifier.send_trade_alert("GridTrading", "BTC/USDT", "buy", 65000)
# ══════════════════════════════════════════════════════════════

import os
import time
import threading
from datetime import datetime, timezone
from typing import Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore


class TelegramNotifier:
    """
    Notificateur Telegram centralisé pour toutes les stratégies.

    PRINCIPE ANIS SOLIDSCALE :
    - Un seul notificateur partagé par toutes les stratégies
    - Rate limiting automatique (max 20 msg/min)
    - Mode silencieux si non configuré (pas de crash)
    - Messages formatés en Markdown pour lisibilité
    """

    # ── Rate limiting : max 20 messages par minute ──
    MAX_MESSAGES_PER_MINUTE = 20
    RATE_WINDOW_SECONDS = 60

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enabled: bool = True,
    ):
        """
        Initialise le notificateur Telegram.

        Args:
            bot_token: Token du bot Telegram. Si None, lit TELEGRAM_BOT_TOKEN.
            chat_id: ID du chat/groupe. Si None, lit TELEGRAM_CHAT_ID.
            enabled: Si False, désactive complètement les notifications.
        """
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.enabled = enabled and bool(self.bot_token) and bool(self.chat_id)
        self._lock = threading.Lock()
        # ── Historique des envois pour rate limiting ──
        self._send_times: list[float] = []

        if not self.enabled:
            print(
                "[TelegramNotifier] Désactivé : bot_token ou chat_id manquant. "
                "Définissez TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID."
            )

    def _check_rate_limit(self) -> bool:
        """
        Vérifie si on peut envoyer un message sans dépasser le rate limit.

        CHOIX : On utilise une fenêtre glissante plutôt qu'un compteur fixe
        pour être plus précis et éviter les bursts en fin de fenêtre.
        """
        now = time.time()
        # Nettoyer les timestamps hors de la fenêtre
        self._send_times = [
            t for t in self._send_times
            if now - t < self.RATE_WINDOW_SECONDS
        ]
        return len(self._send_times) < self.MAX_MESSAGES_PER_MINUTE

    def _send_raw(self, text: str, parse_mode: str = "Markdown") -> bool:
        """
        Envoie un message brut via l'API Telegram.

        CHOIX : On utilise requests.post synchrone car :
        - Les notifications ne doivent pas bloquer le trading
        - Le rate limiting empêche le spam
        - La simplicité est préférée à la complexité async ici

        Returns:
            True si envoyé avec succès, False sinon.
        """
        if not self.enabled or requests is None:
            return False

        with self._lock:
            if not self._check_rate_limit():
                print("[TelegramNotifier] Rate limit atteint, message ignoré.")
                return False

            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                payload = {
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                }
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    self._send_times.append(time.time())
                    return True
                else:
                    print(
                        f"[TelegramNotifier] Erreur API: {resp.status_code} "
                        f"{resp.text[:200]}"
                    )
                    return False
            except Exception as e:
                print(f"[TelegramNotifier] Erreur d'envoi: {e}")
                return False

    # ══════════════════════════════════════════════════════════
    # MÉTHODES PUBLIQUES — Utilisées par toutes les stratégies
    # ══════════════════════════════════════════════════════════

    def send_message(self, message: str) -> bool:
        """Envoie un message texte simple."""
        return self._send_raw(message)

    def send_trade_alert(
        self,
        strategy_name: str,
        pair: str,
        side: str,
        price: float,
        amount: float = 0.0,
        pnl: float = 0.0,
        dry_run: bool = True,
    ) -> bool:
        """
        Envoie une alerte de trade formatée.

        Utilisé par TradeLogger après chaque log_trade().
        Format visuellement clair pour lecture rapide sur mobile.
        """
        mode = "🧪 DRY RUN" if dry_run else "🔴 LIVE"
        emoji = "🟢" if side.lower() == "buy" else "🔴"
        pnl_str = f"+{pnl:.2f}" if pnl >= 0 else f"{pnl:.2f}"

        text = (
            f"{emoji} *{strategy_name}* | {mode}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Paire : `{pair}`\n"
            f"📌 Side : *{side.upper()}*\n"
            f"💰 Prix : `{price:.8g}`\n"
            f"📦 Quantité : `{amount:.8g}`\n"
            f"📈 PnL : `{pnl_str} USDT`\n"
            f"🕐 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        return self._send_raw(text)

    def send_performance_report(
        self,
        strategy_name: str,
        win_rate: float,
        total_trades: int,
        total_pnl: float,
        max_drawdown: float,
        period: str = "Hebdomadaire",
    ) -> bool:
        """
        Envoie un rapport de performance formaté.

        Utilisé par PerformanceTracker.generate_weekly_report().
        """
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
        pnl_str = f"+{total_pnl:.2f}" if total_pnl >= 0 else f"{total_pnl:.2f}"

        text = (
            f"📋 *Rapport {period}*\n"
            f"🤖 Stratégie : *{strategy_name}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Win Rate : `{win_rate:.1f}%`\n"
            f"📊 Total Trades : `{total_trades}`\n"
            f"{pnl_emoji} PnL Total : `{pnl_str} USDT`\n"
            f"⚠️ Max Drawdown : `{max_drawdown:.2f}%`\n"
            f"🕐 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        return self._send_raw(text)

    def send_error_alert(
        self,
        strategy_name: str,
        error_message: str,
    ) -> bool:
        """
        Envoie une alerte d'erreur critique.

        Utilisé quand une stratégie rencontre une erreur irrécupérable.
        """
        text = (
            f"🚨 *ERREUR CRITIQUE*\n"
            f"🤖 Stratégie : *{strategy_name}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"❌ `{error_message[:500]}`\n"
            f"🕐 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        return self._send_raw(text)

    def send_startup_message(self, strategy_name: str, dry_run: bool = True) -> bool:
        """Notification de démarrage d'une stratégie."""
        mode = "🧪 DRY RUN" if dry_run else "🔴 LIVE"
        text = (
            f"🚀 *Démarrage* | {mode}\n"
            f"🤖 Stratégie : *{strategy_name}*\n"
            f"🕐 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        return self._send_raw(text)
