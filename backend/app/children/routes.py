"""Child profiles and parent-granted educator access."""


from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import get_child_for_user
from app.audit import AuditEventType, AuditLogger
from app.auth.deps import get_current_user, require_roles
from app.core.rate_limit import limiter
from app.core.time import utcnow
from app.database import get_db
from app.models import ChildProfile, EducatorLearnerAssignment, User
from app.privacy.service import delete_children
from app.schemas import ChildCreate, ChildResponse, ChildUpdate, EducatorGrantCreate, EducatorGrantResponse

router = APIRouter(prefix="/api/children", tags=["children"])

MAX_CHILDREN_PER_ACCOUNT = 20


@router.post("", response_model=ChildResponse, status_code=status.HTTP_201_CREATED)
def create_child(payload: ChildCreate, request: Request, user: User = Depends(require_roles("parent")), db: Session = Depends(get_db)) -> ChildProfile:
    owned = db.scalars(select(ChildProfile.id).where(ChildProfile.owner_id == user.id)).all()
    if len(owned) >= MAX_CHILDREN_PER_ACCOUNT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"An account can have at most {MAX_CHILDREN_PER_ACCOUNT} child profiles")
    child = ChildProfile(owner_id=user.id, **payload.model_dump())
    db.add(child)
    db.commit()
    db.refresh(child)
    AuditLogger(request).log(AuditEventType.CHILD_CREATE, user_id=str(user.id), resource_type="child", resource_id=str(child.id))
    return child


@router.get("", response_model=list[ChildResponse])
def list_children(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ChildProfile]:
    return list(db.scalars(select(ChildProfile).where(ChildProfile.owner_id == user.id).order_by(ChildProfile.created_at.desc())))


@router.get("/{child_id}", response_model=ChildResponse)
def get_child(child_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ChildProfile:
    return get_child_for_user(db, user, child_id)


@router.patch("/{child_id}", response_model=ChildResponse)
def update_child(child_id: UUID, payload: ChildUpdate, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ChildProfile:
    child = get_child_for_user(db, user, child_id)
    changes = payload.model_dump(exclude_unset=True)
    if "display_name" in changes:
        name = (changes["display_name"] or "").strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Display name is required")
        child.display_name = name
    if "birth_year" in changes:
        child.birth_year = changes["birth_year"]
    db.commit()
    db.refresh(child)
    AuditLogger(request).log(AuditEventType.CHILD_UPDATE, user_id=str(user.id), resource_type="child", resource_id=str(child.id))
    return child


@router.delete("/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_child(child_id: UUID, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    child = get_child_for_user(db, user, child_id)
    delete_children(db, [child.id])
    db.commit()
    AuditLogger(request).log(AuditEventType.CHILD_DELETE, user_id=str(user.id), resource_type="child", resource_id=str(child_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _grant_response(assignment: EducatorLearnerAssignment) -> EducatorGrantResponse:
    return EducatorGrantResponse(
        child_id=assignment.child_id,
        educator_id=assignment.educator_id,
        educator_display_name=assignment.educator.display_name,
        status=assignment.status,
        created_at=assignment.created_at,
    )


@router.get("/{child_id}/educators", response_model=list[EducatorGrantResponse])
def list_educator_grants(child_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[EducatorGrantResponse]:
    child = get_child_for_user(db, user, child_id)
    assignments = db.scalars(
        select(EducatorLearnerAssignment)
        .where(EducatorLearnerAssignment.child_id == child.id, EducatorLearnerAssignment.status == "active")
        .order_by(EducatorLearnerAssignment.created_at.desc())
    )
    return [_grant_response(assignment) for assignment in assignments]


@router.post("/{child_id}/educators", response_model=EducatorGrantResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def grant_educator(child_id: UUID, payload: EducatorGrantCreate, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> EducatorGrantResponse:
    """The child's owner shares read-only learner summaries with an educator account."""
    child = get_child_for_user(db, user, child_id)
    educator = db.scalar(select(User).where(User.email == payload.educator_email, User.role == "educator", User.is_active.is_(True)))
    if educator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active educator account uses that email")
    assignment = db.scalar(select(EducatorLearnerAssignment).where(EducatorLearnerAssignment.educator_id == educator.id, EducatorLearnerAssignment.child_id == child.id, EducatorLearnerAssignment.status == "active"))
    if assignment is None:
        # Reuse a revoked row if one exists (unique index covers educator/child/status).
        assignment = db.scalar(select(EducatorLearnerAssignment).where(EducatorLearnerAssignment.educator_id == educator.id, EducatorLearnerAssignment.child_id == child.id))
        if assignment is None:
            assignment = EducatorLearnerAssignment(educator_id=educator.id, child_id=child.id, status="active")
            db.add(assignment)
        else:
            assignment.status = "active"
            assignment.revoked_at = None
            assignment.revocation_reason = None
            assignment.created_at = utcnow()
        db.commit()
        db.refresh(assignment)
    AuditLogger(request).log(AuditEventType.EDUCATOR_AUTHORIZE, user_id=str(user.id), resource_type="child", resource_id=str(child.id), details={"educator_id": str(educator.id)})
    return _grant_response(assignment)


@router.delete("/{child_id}/educators/{educator_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_educator(child_id: UUID, educator_id: UUID, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    child = get_child_for_user(db, user, child_id)
    assignment = db.scalar(select(EducatorLearnerAssignment).where(EducatorLearnerAssignment.educator_id == educator_id, EducatorLearnerAssignment.child_id == child.id, EducatorLearnerAssignment.status == "active"))
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Educator access not found")
    assignment.status = "revoked"
    assignment.revoked_at = utcnow()
    assignment.revocation_reason = "owner revocation"
    db.commit()
    AuditLogger(request).log(AuditEventType.EDUCATOR_REVOKE, user_id=str(user.id), resource_type="child", resource_id=str(child.id), details={"educator_id": str(educator_id)})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
