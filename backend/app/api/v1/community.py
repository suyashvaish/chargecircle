from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.community import (
    Conversation,
    Dispute,
    Favorite,
    Message,
    Notification,
    Review,
)
from app.models.enums import BookingStatus
from app.models.marketplace import Booking, ChargingSession, HomeChargerListing
from app.models.user import User
from app.schemas.community import (
    ConversationOut,
    DisputeCreate,
    DisputeOut,
    FavoriteCreate,
    FavoriteOut,
    MessageCreate,
    MessageOut,
    NotificationOut,
    ReviewCreate,
    ReviewHostResponse,
    ReviewOut,
)
from app.services.auth_service import get_current_user
from app.services.audit import audit
from app.services.notification_service import send_in_app_notification

router = APIRouter(prefix="/community", tags=["Reviews, Messaging & Favorites"])


def _public_name(full_name: str) -> str:
    """Public reviews show a first name and last initial only."""
    parts = (full_name or "EV Driver").split()
    return parts[0] + (f" {parts[-1][0]}." if len(parts) > 1 else "")


@router.post("/reviews", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def submit_review(
    data: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submits a review for an eligible completed charging session."""
    booking = db.query(Booking).filter(Booking.id == data.booking_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if booking.driver_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the driver can review this session")

    if booking.status != BookingStatus.COMPLETED.value or not booking.session or booking.session.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reviews can only be submitted after completing the charging session"
        )

    existing_review = db.query(Review).filter(Review.booking_id == booking.id).first()
    if existing_review:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already reviewed this booking")

    review = Review(
        booking_id=booking.id,
        driver_id=current_user.id,
        listing_id=booking.listing_id,
        rating_overall=data.rating_overall,
        rating_accuracy=data.rating_accuracy,
        rating_host=data.rating_host,
        rating_parking=data.rating_parking,
        comment=data.comment
    )
    db.add(review)
    audit(db, current_user.id, "REVIEW_SUBMITTED", "Review", booking.id)
    db.commit()
    db.refresh(review)

    return ReviewOut(
        id=review.id,
        booking_id=review.booking_id,
        driver_name=_public_name(current_user.full_name),
        listing_id=review.listing_id,
        rating_overall=review.rating_overall,
        rating_accuracy=review.rating_accuracy,
        rating_host=review.rating_host,
        rating_parking=review.rating_parking,
        comment=review.comment,
        created_at=review.created_at
    )


@router.get("/listings/{listing_id}/reviews", response_model=List[ReviewOut])
def get_listing_reviews(listing_id: int, db: Session = Depends(get_db)):
    """Retrieves verified reviews for a specific home charging facility."""
    reviews = db.query(Review).filter(Review.listing_id == listing_id, Review.moderation_status == "published").all()
    results: List[ReviewOut] = []
    for r in reviews:
        results.append(
            ReviewOut(
                id=r.id,
                booking_id=r.booking_id,
                driver_name=_public_name(r.driver.full_name) if r.driver else "EV Driver",
                listing_id=r.listing_id,
                rating_overall=r.rating_overall,
                rating_accuracy=r.rating_accuracy,
                rating_host=r.rating_host,
                rating_parking=r.rating_parking,
                comment=r.comment,
                host_response=r.host_response,
                host_responded_at=r.host_responded_at,
                created_at=r.created_at
            )
        )
    return results


@router.post("/reviews/{review_id}/response", response_model=ReviewOut)
def respond_to_review(
    review_id: int,
    data: ReviewHostResponse,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Allows the host to respond to a customer review."""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    if review.listing.host_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the host can respond to this review")

    review.host_response = data.response
    review.host_responded_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(review)

    return ReviewOut(
        id=review.id,
        booking_id=review.booking_id,
        driver_name=_public_name(review.driver.full_name),
        listing_id=review.listing_id,
        rating_overall=review.rating_overall,
        rating_accuracy=review.rating_accuracy,
        rating_host=review.rating_host,
        rating_parking=review.rating_parking,
        comment=review.comment,
        host_response=review.host_response,
        host_responded_at=review.host_responded_at,
        created_at=review.created_at
    )


@router.post("/favorites", response_model=FavoriteOut)
def toggle_favorite(
    data: FavoriteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggles bookmarking a public station or home charging facility."""
    query = db.query(Favorite).filter(Favorite.user_id == current_user.id)
    if data.station_id:
        query = query.filter(Favorite.station_id == data.station_id)
    elif data.home_listing_id:
        query = query.filter(Favorite.home_listing_id == data.home_listing_id)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target ID required")

    existing = query.first()
    if existing:
        db.delete(existing)
        db.commit()
        return FavoriteOut(
            id=0,
            user_id=current_user.id,
            station_id=data.station_id,
            home_listing_id=data.home_listing_id,
            title="Removed",
            created_at=datetime.now(timezone.utc)
        )

    fav = Favorite(
        user_id=current_user.id,
        station_id=data.station_id,
        home_listing_id=data.home_listing_id
    )
    db.add(fav)
    db.commit()
    db.refresh(fav)

    title = fav.station.name if fav.station else (fav.home_listing.title if fav.home_listing else "Saved Charger")
    addr = fav.station.address if fav.station else (fav.home_listing.locality if fav.home_listing else "")

    return FavoriteOut(
        id=fav.id,
        user_id=fav.user_id,
        station_id=fav.station_id,
        home_listing_id=fav.home_listing_id,
        title=title,
        address=addr,
        created_at=fav.created_at
    )


@router.get("/favorites", response_model=List[FavoriteOut])
def list_favorites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists saved charging stations and home chargers."""
    favs = db.query(Favorite).filter(Favorite.user_id == current_user.id).all()
    results: List[FavoriteOut] = []
    for f in favs:
        title = f.station.name if f.station else (f.home_listing.title if f.home_listing else "Saved Charger")
        addr = f.station.address if f.station else (f.home_listing.locality if f.home_listing else "")
        results.append(
            FavoriteOut(
                id=f.id,
                user_id=f.user_id,
                station_id=f.station_id,
                home_listing_id=f.home_listing_id,
                title=title,
                address=addr,
                created_at=f.created_at
            )
        )
    return results


@router.post("/disputes", response_model=DisputeOut, status_code=status.HTTP_201_CREATED)
def file_dispute(
    data: DisputeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Files a formal dispute regarding a paid booking session. One open dispute per booking per person."""
    booking = db.query(Booking).filter(Booking.id == data.booking_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    is_driver = booking.driver_id == current_user.id
    is_host = booking.listing.host_id == current_user.id
    if not (is_driver or is_host):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized booking access")
    if booking.status not in (BookingStatus.CONFIRMED.value, BookingStatus.IN_PROGRESS.value,
                              BookingStatus.COMPLETED.value, BookingStatus.CANCELLED.value, BookingStatus.DISPUTED.value) \
            or not booking.payment or booking.payment.status not in ("captured", "refunded"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Disputes can only be filed for bookings that were paid")
    if db.query(Dispute).filter(Dispute.booking_id == booking.id, Dispute.filed_by_id == current_user.id,
                                Dispute.status.in_(["open", "escalated"])).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already have an open dispute for this booking")

    against_id = booking.listing.host_id if is_driver else booking.driver_id
    dispute = Dispute(
        booking_id=booking.id, filed_by_id=current_user.id, against_id=against_id, reason=data.reason,
        category=data.category, evidence_url=data.evidence_url,
        prior_booking_status=booking.status, prior_session_status=booking.session.status if booking.session else None)
    db.add(dispute)
    if booking.status in (BookingStatus.CONFIRMED.value, BookingStatus.IN_PROGRESS.value, BookingStatus.COMPLETED.value):
        booking.status = BookingStatus.DISPUTED.value
        if booking.session and booking.session.status != "cancelled":
            booking.session.status = "disputed"
    audit(db, current_user.id, "DISPUTE_FILED", "Booking", booking.id, {"category": data.category})
    send_in_app_notification(db, against_id, "A dispute was filed", f"A dispute was opened on booking {booking.booking_reference}. Our team will review it.",
                             "dispute_filed", f"/bookings/{booking.id}", commit=False)
    db.commit()
    db.refresh(dispute)
    return dispute


@router.get("/notifications", response_model=List[NotificationOut])
def get_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves user notifications."""
    return db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.created_at.desc()).limit(30).all()


@router.put("/notifications/{notif_id}/read")
def mark_notification_read(
    notif_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Marks a notification as read."""
    notif = db.query(Notification).filter(
        Notification.id == notif_id,
        Notification.user_id == current_user.id
    ).first()
    if notif:
        notif.is_read = True
        db.commit()
    return {"status": "success"}


@router.post("/messages", response_model=MessageOut)
def send_message(
    data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Sends a booking-linked or direct message between driver and host."""
    if data.recipient_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot message yourself")
    related = db.query(Booking).join(HomeChargerListing).filter(
        ((Booking.driver_id == current_user.id) & (HomeChargerListing.host_id == data.recipient_id)) |
        ((Booking.driver_id == data.recipient_id) & (HomeChargerListing.host_id == current_user.id))).first()
    if not related:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only message a host or driver you share a booking with")
    # Find or create conversation
    p1, p2 = min(current_user.id, data.recipient_id), max(current_user.id, data.recipient_id)
    conv = db.query(Conversation).filter(
        Conversation.participant_one_id == p1,
        Conversation.participant_two_id == p2
    ).first()

    if not conv:
        conv = Conversation(
            booking_id=data.booking_id,
            participant_one_id=p1,
            participant_two_id=p2
        )
        db.add(conv)
        db.flush()

    msg = Message(
        conversation_id=conv.id,
        sender_id=current_user.id,
        content=data.content
    )
    db.add(msg)
    conv.last_message_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)

    return MessageOut(
        id=msg.id,
        conversation_id=msg.conversation_id,
        sender_id=msg.sender_id,
        sender_name=current_user.full_name,
        content=msg.content,
        is_read=msg.is_read,
        created_at=msg.created_at
    )


@router.get("/conversations", response_model=List[ConversationOut])
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists recent conversations for the current user."""
    convs = db.query(Conversation).filter(
        (Conversation.participant_one_id == current_user.id) |
        (Conversation.participant_two_id == current_user.id)
    ).order_by(Conversation.last_message_at.desc()).all()

    results: List[ConversationOut] = []
    for c in convs:
        other_id = c.participant_two_id if c.participant_one_id == current_user.id else c.participant_one_id
        other_user = db.query(User).filter(User.id == other_id).first()
        last_msg = c.messages[-1].content if c.messages else "No messages"
        unread = sum(1 for m in c.messages if m.sender_id != current_user.id and not m.is_read)

        results.append(
            ConversationOut(
                id=c.id,
                booking_id=c.booking_id,
                other_participant_id=other_id,
                other_participant_name=other_user.full_name if other_user else "User",
                last_message=last_msg,
                last_message_at=c.last_message_at,
                unread_count=unread
            )
        )
    return results
