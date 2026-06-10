from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.middleware.firebase_auth import get_current_user, CurrentUser, require_roles
from app.models.document import DocumentTemplate, GeneratedDocument, DocumentType, DocumentStatus
from app.utils.minio_client import upload_bytes, download_bytes, get_presigned_url
from app.utils.audit_logger import log_action
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

router = APIRouter(prefix="/documents", tags=["Documents"])

class TemplateCreate(BaseModel):
    name: str
    type: str
    content_template: str
    allowed_roles: List[str]

class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    content_template: Optional[str] = None
    allowed_roles: Optional[List[str]] = None

class DocumentGenerate(BaseModel):
    template_id: str
    employee_id: str

def template_to_dict(t: DocumentTemplate) -> dict:
    return {
        "id": str(t.id),
        "name": t.name,
        "type": t.type,
        "content_template": t.content_template,
        "allowed_roles": t.allowed_roles,
        "created_at": str(t.created_at) if t.created_at else None,
    }

def doc_to_dict(d: GeneratedDocument) -> dict:
    return {
        "id": str(d.id),
        "employee_id": str(d.employee_id),
        "template_id": str(d.template_id) if d.template_id else None,
        "generated_by": str(d.generated_by),
        "generated_at": str(d.generated_at),
        "minio_path": d.minio_path,
        "status": d.status,
        "rh_validated_by": str(d.rh_validated_by) if d.rh_validated_by else None,
        "rh_validated_at": str(d.rh_validated_at) if d.rh_validated_at else None,
    }

# ---- Templates ----

@router.get("/templates/")
async def list_templates(
    type: Optional[str] = Query(None),
    role_access: Optional[str] = Query(None),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(DocumentTemplate)
    if type:
        q = q.where(DocumentTemplate.type == type)
    result = await db.execute(q)
    templates = result.scalars().all()
    
    # Filter based on role access
    role = role_access or user.role
    filtered = [t for t in templates if not t.allowed_roles or role in t.allowed_roles]
    return {"data": [template_to_dict(t) for t in filtered]}

@router.post("/templates/")
async def create_template(
    payload: TemplateCreate,
    user: CurrentUser = Depends(require_roles("rh", "admin")),
    db: AsyncSession = Depends(get_db),
):
    template = DocumentTemplate(
        id=uuid.uuid4(),
        name=payload.name,
        type=DocumentType(payload.type),
        content_template=payload.content_template,
        allowed_roles=payload.allowed_roles,
    )
    db.add(template)
    await db.flush()
    await log_action(db, user.uid, "CREATE", "document_template", str(template.id))
    return {"data": template_to_dict(template)}

@router.put("/templates/{template_id}")
async def update_template(
    template_id: str,
    payload: TemplateUpdate,
    user: CurrentUser = Depends(require_roles("rh", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DocumentTemplate).where(DocumentTemplate.id == uuid.UUID(template_id)))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template non trouvé")
    
    if payload.name:
        t.name = payload.name
    if payload.content_template:
        t.content_template = payload.content_template
    if payload.allowed_roles:
        t.allowed_roles = payload.allowed_roles
        
    await log_action(db, user.uid, "UPDATE", "document_template", template_id)
    return {"data": template_to_dict(t)}

@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    user: CurrentUser = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DocumentTemplate).where(DocumentTemplate.id == uuid.UUID(template_id)))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template non trouvé")
    await db.delete(t)
    await log_action(db, user.uid, "DELETE", "document_template", template_id)
    return {"message": "Template supprimé"}

# ---- Generated Documents ----

@router.get("/")
async def list_my_documents(
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.employee_id:
        return {"data": []}
    q = select(GeneratedDocument).where(GeneratedDocument.employee_id == uuid.UUID(user.employee_id))
    if status:
        q = q.where(GeneratedDocument.status == status)
    result = await db.execute(q)
    return {"data": [doc_to_dict(d) for d in result.scalars()]}

@router.get("/all")
async def list_all_documents(
    employee_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user: CurrentUser = Depends(require_roles("rh", "admin")),
    db: AsyncSession = Depends(get_db),
):
    q = select(GeneratedDocument)
    if employee_id:
        q = q.where(GeneratedDocument.employee_id == uuid.UUID(employee_id))
    if status:
        q = q.where(GeneratedDocument.status == status)
    result = await db.execute(q)
    return {"data": [doc_to_dict(d) for d in result.scalars()]}

@router.post("/generate")
async def generate_document(
    payload: DocumentGenerate,
    user: CurrentUser = Depends(require_roles("collaborateur", "rh")),
    db: AsyncSession = Depends(get_db),
):
    # Retrieve template
    t_result = await db.execute(select(DocumentTemplate).where(DocumentTemplate.id == uuid.UUID(payload.template_id)))
    template = t_result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template non trouvé")
        
    # Generate content (Mock IA generation)
    content_raw = f"Document généré le {datetime.now()} basé sur le template: {template.name}"
    
    # Save a placeholder PDF to MinIO
    object_name = f"docs/{uuid.uuid4()}.pdf"
    placeholder_pdf = b"%PDF-1.4 Mock Generated Document PDF"
    minio_path = upload_bytes("humanai-documents", object_name, placeholder_pdf, "application/pdf")
    
    doc = GeneratedDocument(
        id=uuid.uuid4(),
        employee_id=uuid.UUID(payload.employee_id),
        template_id=template.id,
        generated_by=uuid.UUID(user.uid) if len(user.uid) == 36 else uuid.uuid4(),
        content_snapshot=content_raw,
        minio_path=minio_path,
        status=DocumentStatus.draft,
    )
    db.add(doc)
    await db.flush()
    await log_action(db, user.uid, "GENERATE", "document", str(doc.id))
    return {"data": doc_to_dict(doc)}

@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(GeneratedDocument).where(GeneratedDocument.id == uuid.UUID(doc_id)))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")
        
    # Check ownership
    if user.role not in ["rh", "admin"] and str(doc.employee_id) != user.employee_id:
        raise HTTPException(status_code=403, detail="Accès interdit")
        
    return {"data": doc_to_dict(doc)}

@router.get("/{doc_id}/download")
async def download_document(
    doc_id: str,
    format: Optional[str] = Query("pdf"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(GeneratedDocument).where(GeneratedDocument.id == uuid.UUID(doc_id)))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")
        
    if user.role not in ["rh", "admin"] and str(doc.employee_id) != user.employee_id:
        raise HTTPException(status_code=403, detail="Accès interdit")
        
    # Download from MinIO
    try:
        bucket, obj_name = doc.minio_path.split("/", 1)
        pdf_data = download_bytes(bucket, obj_name)
    except Exception:
        pdf_data = b"%PDF-1.4 Mock Fallback PDF data"
        
    return Response(
        content=pdf_data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=document_{doc_id}.pdf"},
    )

@router.post("/{doc_id}/validate")
async def validate_document(
    doc_id: str,
    payload: dict = {},
    user: CurrentUser = Depends(require_roles("rh")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(GeneratedDocument).where(GeneratedDocument.id == uuid.UUID(doc_id)))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")
        
    doc.status = DocumentStatus.validated
    doc.rh_validated_by = uuid.UUID(user.uid) if len(user.uid) == 36 else uuid.uuid4()
    doc.rh_validated_at = datetime.utcnow()
    
    await log_action(db, user.uid, "VALIDATE", "document", doc_id)
    return {"message": "Document validé", "data": doc_to_dict(doc)}

@router.post("/{doc_id}/reject")
async def reject_document(
    doc_id: str,
    payload: dict = {},
    user: CurrentUser = Depends(require_roles("rh")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(GeneratedDocument).where(GeneratedDocument.id == uuid.UUID(doc_id)))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")
        
    doc.status = DocumentStatus.rejected
    doc.rejection_reason = payload.get("motif", "Rejeté par la RH")
    
    await log_action(db, user.uid, "REJECT", "document", doc_id)
    return {"message": "Document rejeté", "data": doc_to_dict(doc)}

@router.delete("/{doc_id}")
async def archive_document(
    doc_id: str,
    user: CurrentUser = Depends(require_roles("admin", "rh")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(GeneratedDocument).where(GeneratedDocument.id == uuid.UUID(doc_id)))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")
        
    doc.status = DocumentStatus.archived
    await log_action(db, user.uid, "ARCHIVE", "document", doc_id)
    return {"message": "Document archivé"}
