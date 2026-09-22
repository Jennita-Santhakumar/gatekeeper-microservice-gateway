"""Authentication routes: register and login against the gateway's local auth table.

See core/db.py and core/models.py for why the gateway keeps its own small
credentials table (`gateway_users`) separate from users-service's business
"users" table. Registration is best-effort synced to users-service: if that
service is unreachable, local registration still succeeds (correlated later
by email) and a warning is logged.
"""

from __future__ import annotations

import logging

import requests
from flask import Blueprint, jsonify, request

from core.circuit import USERS_SERVICE_URL
from core.db import SessionLocal
from core.models import GatewayUser
from core.security import create_access_token, hash_password, verify_password

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or "@" not in email:
        return jsonify({"error": "A valid email is required"}), 400
    if not password or len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    session = SessionLocal()
    try:
        existing = session.query(GatewayUser).filter_by(email=email).first()
        if existing is not None:
            return jsonify({"error": "A user with this email already exists"}), 409

        user = GatewayUser(email=email, password_hash=hash_password(password))
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id
    finally:
        session.close()

    # Best-effort sync to users-service's business-data record. Failure here
    # must not fail auth registration — the gateway can still authenticate
    # this user independently; correlation happens later by email.
    try:
        resp = requests.post(
            f"{USERS_SERVICE_URL}/users",
            # users-service requires a username distinct from email; the local
            # part of the email is used as a reasonable default. The password
            # is forwarded once, at registration time, so users-service can
            # store its own independent hash -- it is never persisted or
            # logged here, only relayed over the (in-cluster) HTTP call.
            json={"email": email, "username": email.split("@")[0], "password": password},
            timeout=3,
        )
        if not resp.ok:
            logger.warning(
                "users-service rejected business record creation for %s: %s %s",
                email,
                resp.status_code,
                resp.text[:200],
            )
    except requests.exceptions.RequestException as exc:
        logger.warning("users-service unreachable during registration sync for %s: %s", email, exc)

    token = create_access_token(user_id=user_id, email=email)
    return jsonify({"id": user_id, "email": email, "access_token": token}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    session = SessionLocal()
    try:
        user = session.query(GatewayUser).filter_by(email=email).first()
        if user is None or not verify_password(password, user.password_hash):
            return jsonify({"error": "Invalid email or password"}), 401
        user_id = user.id
    finally:
        session.close()

    token = create_access_token(user_id=user_id, email=email)
    return jsonify({"access_token": token, "token_type": "bearer"}), 200
