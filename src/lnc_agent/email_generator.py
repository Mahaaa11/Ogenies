import os

from .models import Prospect, Recommendation, EmailDraft
from .experiments import choose_ab_variant
from .senders import choose_sender_email
from .models import Event
from .timing import choose_best_send_hour
from .openai_responses import OpenAIError, responses_json


def generate_email_draft(recommendation: Recommendation, events: list[Event] | None = None) -> EmailDraft:
    prospect = recommendation.prospect
    from_email = choose_sender_email(prospect.id)
    template_id = os.environ.get("LNC_SENDGRID_TEMPLATE_ID", "").strip()
    variant = choose_ab_variant(prospect.id)
    send_hour = choose_best_send_hour(events or [], default_hour=9)
    use_openai = os.environ.get("LNC_USE_OPENAI", "").strip().lower() in ("1", "true", "yes", "y")
    model = os.environ.get("LNC_OPENAI_MODEL", "gpt-4.1-mini").strip()

    if recommendation.next_action == "do_not_contact":
        return EmailDraft(
            prospect_id=prospect.id,
            from_email="",
            template_id=template_id,
            dynamic_template_data={},
        )

    if recommendation.segment == "high":
        titre = "Réduisez votre facture d’énergie dès aujourd’hui"
        offre = "Découvrez une offre adaptée à vos besoins"
        lien = "https://www.ogenies.fr/offer/sarah123"
        contenu = (
            f"Chez OGENIS, nous aidons les entreprises comme {prospect.company or 'la vôtre'} "
            "à optimiser leurs dépenses énergétiques et à réaliser des économies durables."
        )
    elif recommendation.segment == "medium":
        titre = "Une optimisation simple, en quelques minutes"
        offre = "Voir un exemple adapté"
        lien = "https://www.ogenies.fr/demo"
        contenu = (
            "Je vous propose un exemple concret pour améliorer la performance de vos campagnes "
            "en utilisant la data pour adresser le bon message au bon moment."
        )
    else:
        titre = "Ressource utile pour améliorer vos résultats"
        offre = "Je découvre la ressource"
        lien = "https://www.ogenies.fr/guide"
        contenu = (
            "Je vous partage une ressource courte sur l’optimisation des campagnes email "
            "avec la data et l’IA : moins d’envois inutiles, plus de messages pertinents."
        )

    prenom = prospect.first_name or ""

    if use_openai and os.environ.get("OPENAI_API_KEY", "").strip():
        try:
            generated = responses_json(
                model=model,
                instructions=(
                    "Tu es un copywriter email marketing francophone pour OGENIES.\n"
                    "Tu écris UNIQUEMENT en français, ton professionnel, concis et persuasif.\n"
                    "Style attendu (proche de l'exemple):\n"
                    "- Titre accrocheur court (type headline)\n"
                    "- Message court qui souligne que le contrat a peut-être augmenté sans que le client le sache\n"
                    "- Promesse: analyse du contrat + analyse du marché + offres à prix fixe\n"
                    "- CTA orienté bénéfice: 'Vérifier mon contrat gratuitement'\n"
                    "- Ajoute une ligne de réassurance: '✓ Gratuit • ✓ Sans engagement • ✓ En 2 minutes'\n"
                    "Réponds STRICTEMENT en JSON valide avec les clés: titre, contenu, offre.\n"
                    "Ne mets aucun texte hors JSON."
                ),
                input_text=(
                    f"Prospect:\n"
                    f"- prenom: {prenom or '(vide)'}\n"
                    f"- entreprise: {prospect.company or '(inconnue)'}\n"
                    f"- role: {prospect.role or '(inconnu)'}\n"
                    f"- secteur: {prospect.industry or '(inconnu)'}\n"
                    f"Segment d'intérêt: {recommendation.segment} (score={recommendation.score}).\n"
                    f"Objectif: générer les variables du template SendGrid."
                ),
            )
            if isinstance(generated.get("titre"), str) and generated["titre"].strip():
                titre = generated["titre"].strip()
            if isinstance(generated.get("contenu"), str) and generated["contenu"].strip():
                contenu = generated["contenu"].strip()
            if isinstance(generated.get("offre"), str) and generated["offre"].strip():
                offre = generated["offre"].strip()
        except OpenAIError:
            # Fallback silently to template-based content.
            pass

    dynamic = {
        "titre": titre,
        "contenu": contenu,
        "lien": f"{lien}?v={variant}",
        "prenom": prenom,
        "offre": offre,
        "variant": variant,
        "send_hour": send_hour,
    }

    return EmailDraft(
        prospect_id=prospect.id,
        from_email=from_email,
        template_id=template_id,
        dynamic_template_data=dynamic,
    )
