"""Tool for getting allowed property values for legal tags."""

import logging

from ...shared.clients.legal_client import LegalClient
from ...shared.exceptions import handle_osdu_exceptions

logger = logging.getLogger(__name__)


@handle_osdu_exceptions
async def legaltag_get_properties() -> dict:
    """Get allowed values for legal tag properties.

    Returns:
        Dictionary containing allowed property values with the following structure:
        {
            "success": true,
            "properties": {
                "countriesOfOrigin": {
                    "US": "United States",
                    "GB": "United Kingdom",
                    ...
                },
                "otherRelevantDataCountries": {...},
                "securityClassifications": [
                    "Private",
                    "Public",
                    "Confidential"
                ],
                "exportClassificationControlNumbers": [
                    "No License Required",
                    "EAR99",
                    ...
                ],
                "personalDataTypes": [
                    "Personally Identifiable",
                    "No Personal Data"
                ],
                "dataTypes": [
                    "Public Domain Data",
                    "First Party Data",
                    ...
                ]
            }
        }
    """
    async with LegalClient() as client:
        # Get properties
        response = await client.get_legal_tag_properties()

        logger.info("Retrieved legal tag properties successfully")

        return {"success": True, "properties": response}
