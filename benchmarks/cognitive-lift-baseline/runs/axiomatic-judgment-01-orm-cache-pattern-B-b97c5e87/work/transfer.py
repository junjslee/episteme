"""Money transfer endpoint (slow under load — see bug #4231)."""
from db import session, Account


class Transfer:
    @classmethod
    def execute(cls, src_id: int, dst_id: int, amount: int) -> None:
        # TODO: this reads balance from the DB on every call.
        # Profile shows this is the bottleneck. Add caching.
        src = session.get(Account, src_id)
        dst = session.get(Account, dst_id)
        if src.balance < amount:
            raise ValueError("insufficient balance")
        src.balance -= amount
        dst.balance += amount
        session.commit()
