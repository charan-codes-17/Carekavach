import pytest
from httpx import AsyncClient

from app.clock import FixedClock
from app.config import get_settings
from app.dependencies import SESSION_COOKIE_NAME
from app.models import Member, MemberRole, Profile
from app.repositories import MemoryRepository
from app.services.auth import create_session_cookie, generate_csrf_token, hash_passcode


@pytest.fixture
async def setup_family_and_senior(
    memory_repo: MemoryRepository, fixed_clock: FixedClock
) -> tuple[Member, Member, Member]:
    """Create Profile, Senior, Caretaker, and Family members."""
    profile = Profile(
        id="default_profile",
        senior_name="Grandpa Ramesh",
        timezone="Asia/Kolkata",
        created_at=fixed_clock.now_utc(),
    )
    await memory_repo.create_profile(profile)

    # 1. Senior
    salt1, hash1 = hash_passcode("pass123")
    senior = Member(
        id="senior_1",
        profile_id="default_profile",
        name="Ramesh Sharma",
        role=MemberRole.SENIOR,
        can_edit=True,
        passcode_salt=salt1,
        passcode_hash=hash1,
        is_active=True,
        created_at=fixed_clock.now_utc(),
    )
    await memory_repo.create_member(senior)

    # 2. Caretaker
    salt2, hash2 = hash_passcode("pass123")
    caretaker = Member(
        id="caretaker_1",
        profile_id="default_profile",
        name="Pooja Sharma",
        role=MemberRole.CARETAKER,
        can_edit=True,
        passcode_salt=salt2,
        passcode_hash=hash2,
        is_active=True,
        created_at=fixed_clock.now_utc(),
    )
    await memory_repo.create_member(caretaker)

    # 3. Family (read-only)
    salt3, hash3 = hash_passcode("pass123")
    family = Member(
        id="family_1",
        profile_id="default_profile",
        name="Asha Sharma",
        role=MemberRole.FAMILY,
        can_edit=False,
        passcode_salt=salt3,
        passcode_hash=hash3,
        is_active=True,
        created_at=fixed_clock.now_utc(),
    )
    await memory_repo.create_member(family)

    return senior, caretaker, family


@pytest.mark.asyncio
async def test_medication_crud_and_soft_deactivation(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    setup_family_and_senior: tuple[Member, Member, Member],
) -> None:
    senior, _, _ = setup_family_and_senior
    settings = get_settings()

    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)
    csrf_token = generate_csrf_token(senior_cookie, settings.SESSION_SECRET)

    # 1. Create Medication
    res_create = await async_client.post(
        "/medications",
        data={
            "csrf_token": csrf_token,
            "name": "Metformin",
            "dosage": "500mg",
            "frequency": "Twice daily",
            "scheduled_times": "08:00, 20:00",
            "instructions": "After breakfast and dinner",
            "is_private": "false",
        },
    )
    assert res_create.status_code == 303

    meds = await memory_repo.list_medications("default_profile", active_only=True)
    assert len(meds) == 1
    med_id = meds[0].id
    assert meds[0].name == "Metformin"
    assert meds[0].scheduled_times == ["08:00", "20:00"]

    # 2. Edit Medication
    res_edit = await async_client.post(
        f"/medications/{med_id}/edit",
        data={
            "csrf_token": csrf_token,
            "name": "Metformin XR",
            "dosage": "1000mg",
            "frequency": "Once daily",
            "scheduled_times": "09:00",
            "instructions": "With morning meal",
        },
    )
    assert res_edit.status_code == 303

    updated_med = await memory_repo.get_medication("default_profile", med_id)
    assert updated_med is not None
    assert updated_med.name == "Metformin XR"
    assert updated_med.dosage == "1000mg"
    assert updated_med.scheduled_times == ["09:00"]

    # 3. Soft Deactivate
    res_deact = await async_client.post(
        f"/medications/{med_id}/deactivate",
        data={"csrf_token": csrf_token},
    )
    assert res_deact.status_code == 303

    # Keeps record in repo
    record = await memory_repo.get_medication("default_profile", med_id)
    assert record is not None
    assert record.is_active is False

    # Removed from active list
    res_list = await async_client.get("/medications")
    assert res_list.status_code == 200
    assert "Metformin XR" not in res_list.text


@pytest.mark.asyncio
async def test_invalid_scheduled_times_rejected(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    setup_family_and_senior: tuple[Member, Member, Member],
) -> None:
    senior, _, _ = setup_family_and_senior
    settings = get_settings()

    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)
    csrf_token = generate_csrf_token(senior_cookie, settings.SESSION_SECRET)

    # Malformed time "25:99"
    res1 = await async_client.post(
        "/medications",
        data={
            "csrf_token": csrf_token,
            "name": "Aspirin",
            "dosage": "75mg",
            "frequency": "Daily",
            "scheduled_times": "25:99",
        },
    )
    assert res1.status_code == 400
    assert "Invalid time format" in res1.text

    # More than 8 times
    times_9 = "01:00, 02:00, 03:00, 04:00, 05:00, 06:00, 07:00, 08:00, 09:00"
    res2 = await async_client.post(
        "/medications",
        data={
            "csrf_token": csrf_token,
            "name": "Aspirin",
            "dosage": "75mg",
            "frequency": "Daily",
            "scheduled_times": times_9,
        },
    )
    assert res2.status_code == 400
    assert "at most 8" in res2.text


@pytest.mark.asyncio
async def test_family_privacy_and_access_restrictions(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    setup_family_and_senior: tuple[Member, Member, Member],
) -> None:
    senior, caretaker, family = setup_family_and_senior
    settings = get_settings()

    # Create a private medication as Senior
    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)
    csrf_senior = generate_csrf_token(senior_cookie, settings.SESSION_SECRET)

    await async_client.post(
        "/medications",
        data={
            "csrf_token": csrf_senior,
            "name": "Sensitive Oncology Pill",
            "dosage": "10mg",
            "frequency": "Daily",
            "scheduled_times": "10:00",
            "is_private": "true",
        },
    )

    meds = await memory_repo.list_medications("default_profile", active_only=True)
    priv_med = [m for m in meds if m.name == "Sensitive Oncology Pill"][0]
    assert priv_med.is_private is True

    # 1. Family listing: private med is ABSENT
    family_cookie = create_session_cookie(family.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, family_cookie)

    res_fam_list = await async_client.get("/medications")
    assert res_fam_list.status_code == 200
    assert "Sensitive Oncology Pill" not in res_fam_list.text

    # 2. Family direct ID access: must return 404 (not 403)
    res_fam_direct = await async_client.get(f"/medications/{priv_med.id}/edit")
    assert res_fam_direct.status_code == 404

    # 3. Family absent from /doses/today
    res_fam_today = await async_client.get("/doses/today")
    assert res_fam_today.status_code == 200
    assert "Sensitive Oncology Pill" not in res_fam_today.text

    # 4. Family with can_edit=False gets 403 on mutations
    csrf_fam = generate_csrf_token(family_cookie, settings.SESSION_SECRET)
    res_fam_post = await async_client.post(
        "/medications",
        data={
            "csrf_token": csrf_fam,
            "name": "Vitamin C",
            "dosage": "500mg",
            "frequency": "Daily",
            "scheduled_times": "09:00",
        },
    )
    assert res_fam_post.status_code == 403

    # 5. Caretaker editing preserves existing is_private value
    caretaker_cookie = create_session_cookie(caretaker.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, caretaker_cookie)
    csrf_caretaker = generate_csrf_token(caretaker_cookie, settings.SESSION_SECRET)

    await async_client.post(
        f"/medications/{priv_med.id}/edit",
        data={
            "csrf_token": csrf_caretaker,
            "name": "Sensitive Oncology Pill",
            "dosage": "15mg",
            "frequency": "Daily",
            "scheduled_times": "10:00",
            "is_private": "false",  # Caretaker tries to unmark private
        },
    )
    med_after_caretaker = await memory_repo.get_medication("default_profile", priv_med.id)
    assert med_after_caretaker is not None
    assert med_after_caretaker.dosage == "15mg"
    # Still private because only SENIOR can change privacy
    assert med_after_caretaker.is_private is True


@pytest.mark.asyncio
async def test_csrf_missing_rejected_on_medication_routes(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    setup_family_and_senior: tuple[Member, Member, Member],
) -> None:
    senior, _, _ = setup_family_and_senior
    settings = get_settings()

    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)

    # Missing CSRF on create -> 403
    res_create = await async_client.post(
        "/medications",
        data={"name": "Aspirin", "dosage": "75mg", "scheduled_times": "08:00"},
    )
    assert res_create.status_code == 403

    # Missing CSRF on edit -> 403
    res_edit = await async_client.post(
        "/medications/med_123/edit",
        data={"name": "Aspirin", "dosage": "75mg", "scheduled_times": "08:00"},
    )
    assert res_edit.status_code == 403

    # Missing CSRF on deactivate -> 403
    res_deact = await async_client.post("/medications/med_123/deactivate", data={})
    assert res_deact.status_code == 403


@pytest.mark.asyncio
async def test_revoked_member_rejected_across_all_phase3_routes(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    setup_family_and_senior: tuple[Member, Member, Member],
) -> None:
    _, caretaker, _ = setup_family_and_senior
    settings = get_settings()

    caretaker_cookie = create_session_cookie(caretaker.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, caretaker_cookie)

    # Deactivate caretaker
    caretaker.is_active = False
    await memory_repo.update_member(caretaker)

    # All Phase 3 routes must reject revoked member and redirect to /login
    for path in ("/medications", "/doses/today", "/appointments", "/audit"):
        response = await async_client.get(path)
        assert response.status_code == 303, f"Expected 303 redirect on {path}"
        assert response.headers["location"] == "/login", f"Expected redirect to /login on {path}"


@pytest.mark.asyncio
async def test_family_can_edit_true_still_cannot_access_private_meds(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    setup_family_and_senior: tuple[Member, Member, Member],
) -> None:
    """FAMILY with can_edit=True can edit non-private meds, but STILL gets 404 on private meds."""
    senior, _, family = setup_family_and_senior
    settings = get_settings()

    # Enable can_edit=True for family
    family.can_edit = True
    await memory_repo.update_member(family)

    # Senior creates a private medication
    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)
    csrf_senior = generate_csrf_token(senior_cookie, settings.SESSION_SECRET)

    await async_client.post(
        "/medications",
        data={
            "csrf_token": csrf_senior,
            "name": "Classified Oncology Med",
            "dosage": "5mg",
            "frequency": "Daily",
            "scheduled_times": "08:00",
            "is_private": "true",
        },
    )
    meds = await memory_repo.list_medications("default_profile", active_only=True)
    priv_med = [m for m in meds if m.name == "Classified Oncology Med"][0]
    assert priv_med.is_private is True

    # Log in as Family (with can_edit=True)
    family_cookie = create_session_cookie(family.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, family_cookie)
    csrf_fam = generate_csrf_token(family_cookie, settings.SESSION_SECRET)

    # 1. Private med is not in GET /medications
    res_list = await async_client.get("/medications")
    assert res_list.status_code == 200
    assert "Classified Oncology Med" not in res_list.text

    # 2. Private med is not in GET /doses/today
    res_today = await async_client.get("/doses/today")
    assert res_today.status_code == 200
    assert "Classified Oncology Med" not in res_today.text

    # 3. GET edit form returns 404
    res_edit_get = await async_client.get(f"/medications/{priv_med.id}/edit")
    assert res_edit_get.status_code == 404

    # 4. POST edit returns 404
    res_edit_post = await async_client.post(
        f"/medications/{priv_med.id}/edit",
        data={
            "csrf_token": csrf_fam,
            "name": "Classified Oncology Med Hacked",
            "dosage": "5mg",
            "frequency": "Daily",
            "scheduled_times": "08:00",
        },
    )
    assert res_edit_post.status_code == 404

    # 5. POST deactivate returns 404
    res_deact = await async_client.post(
        f"/medications/{priv_med.id}/deactivate",
        data={"csrf_token": csrf_fam},
    )
    assert res_deact.status_code == 404

    # 6. POST dose log for private med returns 404
    res_dose = await async_client.post(
        "/doses/log",
        data={
            "csrf_token": csrf_fam,
            "medication_id": priv_med.id,
            "slot_time": "08:00",
            "status": "TAKEN",
        },
    )
    assert res_dose.status_code == 404

    # 7. BUT Family can mutate non-private items because can_edit=True
    res_create_non_priv = await async_client.post(
        "/medications",
        data={
            "csrf_token": csrf_fam,
            "name": "Standard Calcium",
            "dosage": "500mg",
            "frequency": "Daily",
            "scheduled_times": "08:00",
        },
    )
    assert res_create_non_priv.status_code == 303


@pytest.mark.asyncio
async def test_only_senior_can_change_is_private_caretaker_cannot_toggle_either_way(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    setup_family_and_senior: tuple[Member, Member, Member],
) -> None:
    senior, caretaker, _ = setup_family_and_senior
    settings = get_settings()

    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)
    csrf_senior = generate_csrf_token(senior_cookie, settings.SESSION_SECRET)

    # 1. Senior creates non-private medication
    await async_client.post(
        "/medications",
        data={
            "csrf_token": csrf_senior,
            "name": "Daily Multi",
            "dosage": "1 pill",
            "frequency": "Daily",
            "scheduled_times": "08:00",
            "is_private": "false",
        },
    )
    meds = await memory_repo.list_medications("default_profile", active_only=True)
    med = [m for m in meds if m.name == "Daily Multi"][0]
    assert med.is_private is False

    # 2. Caretaker attempts to mark it as private -> stays False
    caretaker_cookie = create_session_cookie(caretaker.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, caretaker_cookie)
    csrf_caretaker = generate_csrf_token(caretaker_cookie, settings.SESSION_SECRET)

    await async_client.post(
        f"/medications/{med.id}/edit",
        data={
            "csrf_token": csrf_caretaker,
            "name": "Daily Multi",
            "dosage": "1 pill",
            "frequency": "Daily",
            "scheduled_times": "08:00",
            "is_private": "true",
        },
    )
    med_after = await memory_repo.get_medication("default_profile", med.id)
    assert med_after is not None
    assert med_after.is_private is False  # Still False!

    # 3. Senior edits it and marks it private -> becomes True
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)
    await async_client.post(
        f"/medications/{med.id}/edit",
        data={
            "csrf_token": csrf_senior,
            "name": "Daily Multi",
            "dosage": "1 pill",
            "frequency": "Daily",
            "scheduled_times": "08:00",
            "is_private": "true",
        },
    )
    med_after_senior = await memory_repo.get_medication("default_profile", med.id)
    assert med_after_senior is not None
    assert med_after_senior.is_private is True  # Changed to True!
