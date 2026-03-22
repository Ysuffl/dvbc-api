# Import all the models, so that Base has them before being
# imported by Alembic or used by create_all
from app.db.base_class import Base # noqa
from app.models.table_booking import Table, Booking, Customer # noqa
from app.models.user import User # noqa
