"""Translation between the domain and the public contract (contracts.access.v1)."""

from datetime import UTC

from contracts.access import v1

from access.domain.curve import CurveAsOf


def to_response(curve: CurveAsOf) -> v1.CurveObservationsResponse:
    return v1.CurveObservationsResponse(
        data=v1.CurveObservations(
            curve_id=curve.curve_id,
            valid_date=curve.valid_date,
            points=[
                v1.CurvePoint(maturity=point.maturity, months=point.months, value=point.value)
                for point in curve.points
            ],
        ),
        meta=v1.CurveMeta(as_of=curve.as_of.astimezone(UTC)),
    )
