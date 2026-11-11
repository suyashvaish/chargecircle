import enum


class UserRoleType(str, enum.Enum):
    DRIVER = "driver"
    HOST = "host"
    OPERATOR = "operator"
    ADMIN = "admin"


class ConnectorType(str, enum.Enum):
    CCS2 = "CCS2"
    TYPE2 = "Type 2"
    GBT = "GB/T"
    BHARAT_AC001 = "Bharat AC-001"
    BHARAT_DC001 = "Bharat DC-001"
    CHADEMO = "CHAdeMO"
    WALL_SOCKET_16A = "16A 3-Pin Socket"


class CurrentType(str, enum.Enum):
    AC = "AC"
    DC = "DC"


class PointStatus(str, enum.Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    OFFLINE = "offline"
    RESERVED = "reserved"
    FAULTED = "faulted"


class ListingStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_VERIFICATION = "pending_verification"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class PropertyType(str, enum.Enum):
    RESIDENTIAL_HOUSE = "residential_house"
    APARTMENT_PARKING = "apartment_parking"
    COMMERCIAL_PARKING = "commercial_parking"
    OFFICE_PARKING = "office_parking"


class EquipmentType(str, enum.Enum):
    DEDICATED_WALLBOX = "dedicated_wallbox"
    PORTABLE_EVSE = "portable_evse"
    INDUSTRIAL_SOCKET = "industrial_socket"


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    AWAITING_PAYMENT = "awaiting_payment"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    PAYMENT_FAILED = "payment_failed"
    DISPUTED = "disputed"


class PaymentStatus(str, enum.Enum):
    CREATED = "created"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


class ReportCategory(str, enum.Enum):
    WORKING_NORMALLY = "working_normally"
    NOT_WORKING = "not_working"
    OCCUPIED = "occupied"
    DAMAGED_EQUIPMENT = "damaged_equipment"
    PAYMENT_TERMINAL_FAILURE = "payment_terminal_failure"
    CONNECTOR_UNAVAILABLE = "connector_unavailable"
    INCORRECT_LOCATION = "incorrect_location"
    CLOSED_STATION = "closed_station"
    INACCURATE_PRICING = "inaccurate_pricing"
    MISLEADING_PRICE = "misleading_price"
    SUSPICIOUS_LISTING = "suspicious_listing"
    UNSAFE_BEHAVIOR = "unsafe_behavior"
    OTHER = "other"


class OperationalStatus(str, enum.Enum):
    CONFIRMED_OPERATIONAL = "Recently confirmed operational"
    LIKELY_OPERATIONAL = "Likely operational"
    REPORTED_UNAVAILABLE = "Reported unavailable"
    CONFLICTING_REPORTS = "Conflicting reports"
    UNKNOWN = "Unknown"
    NOT_RECENTLY_CHECKED = "Not recently checked"


class DisputeStatus(str, enum.Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
