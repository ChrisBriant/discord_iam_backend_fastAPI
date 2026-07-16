def format_reconciliation_log(
    user_import_results,
    user_update_results,
    role_update_results
):

    lines = []

    lines.append("Reconciliation Completed")
    lines.append("")

    lines.append("USER IMPORTS")
    lines.append("------------")

    if user_import_results["inserted"]:
        lines.append("Inserted:")
        for user in user_import_results["inserted"]:
            lines.append(f"  - {user.user_name}")
    else:
        lines.append("Inserted: None")


    lines.append("")
    lines.append("Existing Users:")

    for user in user_import_results["existing"]:
        lines.append(f"  - {user['user']}")
        
        added = user["role_changes"]["added_roles"]
        removed = user["role_changes"]["removed_roles"]

        lines.append(
            f"      Added Roles: {added if added else 'None'}"
        )

        lines.append(
            f"      Removed Roles: {removed if removed else 'None'}"
        )


    lines.append("")
    lines.append("USER CHANGES")
    lines.append("------------")

    lines.append(
        f"Updated: {len(user_update_results['updated'])}"
    )

    lines.append(
        f"Disabled: {len(user_update_results['disabled'])}"
    )


    lines.append("")
    lines.append("ROLE UPDATES")
    lines.append("------------")

    lines.append(
        f"Renamed Roles: {len(role_update_results['renamed_roles'])}"
    )

    lines.append(
        f"Deleted Roles: {len(role_update_results['deleted_roles'])}"
    )


    return "\n".join(lines)