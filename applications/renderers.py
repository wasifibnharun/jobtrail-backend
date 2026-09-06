from rest_framework.renderers import JSONRenderer


class EnvelopeJSONRenderer(JSONRenderer):
    def render(
        self,
        data,
        accepted_media_type=None,
        renderer_context=None,
    ):
        context = renderer_context or {}
        response = context.get("response")
        request = context.get("request")

        if response is None:
            return super().render(
                data,
                accepted_media_type,
                renderer_context,
            )

        if (
            isinstance(data, dict)
            and {"success", "message", "data"} <= data.keys()
        ):
            envelope = data
        else:
            success = 200 <= response.status_code < 400
            envelope = {
                "success": success,
                "message": self.get_message(
                    response,
                    request,
                    data,
                    success,
                ),
                "data": data,
            }

        return super().render(
            envelope,
            accepted_media_type,
            renderer_context,
        )

    @staticmethod
    def get_message(response, request, data, success):
        custom_message = getattr(response, "message", None)

        if custom_message:
            return custom_message

        if not success:
            if isinstance(data, dict):
                detail = data.get("detail")

                if isinstance(detail, str):
                    return detail

                if isinstance(detail, list) and detail:
                    return str(detail[0])

            if response.status_code == 400:
                return "Validation failed."

            return "Request failed."

        if response.status_code == 201:
            return "Created successfully."

        method = getattr(request, "method", "")

        if method in {"PUT", "PATCH"}:
            return "Updated successfully."

        return "Request successful."